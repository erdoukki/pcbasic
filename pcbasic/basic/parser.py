"""
PC-BASIC - parser.py
BASIC code parser

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import string
from collections import deque

from . import error
from . import tokens as tk
from . import statements
from . import operators as op
from . import functions
from . import values

from . import codestream
import sys


class Parser(object):
    """Statement parser."""

    def __init__(self, session, syntax, term):
        """Initialise parser."""
        self.session = session
        # value handler
        self.values = self.session.values
        # temporary string context guard
        self.temp_string = self.session.strings
        # syntax: advanced, pcjr, tandy
        self.syntax = syntax
        # program for TERM command
        self.term = term
        # line number tracing
        self.tron = False
        # pointer position: False for direct line, True for program
        self.run_mode = False
        self.program_code = session.program.bytecode
        if not isinstance(self.program_code, codestream.TokenisedStream):
            print repr(self.program_code)
            sys.exit(0)

        self.current_statement = 0
        # clear stacks
        self.clear_stacks_and_pointers()
        self.init_error_trapping()
        self.error_num = 0
        self.error_pos = 0
        self.statements = statements.Statements(self)
        self.functions = functions.Functions(self)

    def init_error_trapping(self):
        """Initialise error trapping."""
        # True if error handling in progress
        self.error_handle_mode = False
        # statement pointer, run mode of error for RESUME
        self.error_resume = None
        # pointer to error trap
        self.on_error = None

    def parse(self):
        """Parse from the current pointer in current codestream."""
        while True:
            # may raise Break
            self.session.events.check_events()
            try:
                self.handle_basic_events()
                ins = self.get_codestream()
                self.current_statement = ins.tell()
                if not isinstance(ins, codestream.TokenisedStream):
                    print repr(ins), repr(self.program_code), repr(self.session.direct_line)
                    sys.exit(0)

                c = ins.skip_blank()
                # parse line number or : at start of statement
                if c in tk.END_LINE:
                    # line number marker, new statement
                    token = ins.read(5)
                    # end of program or truncated file
                    if token[1:3] == '\0\0' or len(token) < 5:
                        if self.error_resume:
                            # unfinished error handler: no RESUME (don't trap this)
                            self.error_handle_mode = True
                            # get line number right
                            raise error.RunError(error.NO_RESUME, ins.tell()-len(token)-1)
                        # stream has ended
                        self.set_pointer(False)
                        return
                    if self.tron:
                        linenum = self.session.lister.token_to_line_number(token[1:])
                        self.session.screen.write('[' + ('%i' % linenum) + ']')
                    self.session.debugger.debug_step(token)
                elif c == ':':
                    ins.read(1)
                c = ins.skip_blank()
                # empty statement, return to parse next
                if c in tk.END_STATEMENT:
                    continue
                # implicit LET
                elif c in string.ascii_letters:
                    self.statements.exec_let(ins)
                # token
                else:
                    ins.read(1)
                    if c in tk.TWOBYTE:
                        c += ins.read(1)
                    # don't use try-block to avoid catching other KeyErrors in statement
                    if c not in self.statements.statements:
                        raise error.RunError(error.STX)
                    self.statements.statements[c](ins)
            except error.RunError as e:
                self.trap_error(e)

    ###########################################################################
    # clear state

    def clear(self):
        """Clear all to be cleared for CLEAR statement."""
        # clear last error number (ERR) and line number (ERL)
        self.error_num, self.error_pos = 0, 0
        # disable error trapping
        self.init_error_trapping()
        # disable all event trapping (resets PEN to OFF too)
        self.session.events.reset()
        # CLEAR also dumps for_next and while_wend stacks
        self.clear_loop_stacks()
        # reset the DATA pointer
        self.restore()

    def clear_stacks_and_pointers(self):
        """Initialise the stacks and pointers for a new program."""
        # stop running if we were
        self.set_pointer(False)
        # reset loop stacks
        self.clear_stacks()
        # reset program pointer
        self.program_code.seek(0)
        # reset stop/cont
        self.stop = None
        # reset data reader
        self.restore()

    def clear_stacks(self):
        """Clear loop and jump stacks."""
        self.gosub_stack = []
        self.clear_loop_stacks()

    def clear_loop_stacks(self):
        """Clear loop stacks."""
        self.for_stack = []
        self.while_stack = []

    ###########################################################################
    # event and error handling

    def handle_basic_events(self):
        """Jump to user-defined event subs if events triggered."""
        if self.session.events.suspend_all or not self.run_mode:
            return
        for event in self.session.events.all:
            if (event.enabled and event.triggered
                    and not event.stopped and event.gosub is not None):
                # release trigger
                event.triggered = False
                # stop this event while handling it
                event.stopped = True
                # execute 'ON ... GOSUB' subroutine;
                # attach handler to allow un-stopping event on RETURN
                self.jump_gosub(event.gosub, event)

    def trap_error(self, e):
        """Handle a BASIC error through trapping."""
        if e.pos is None:
            if self.run_mode:
                e.pos = self.program_code.tell()-1
            else:
                e.pos = -1
        self.error_num = e.err
        self.error_pos = e.pos
        # don't jump if we're already busy handling an error
        if self.on_error is not None and self.on_error != 0 and not self.error_handle_mode:
            self.error_resume = self.current_statement, self.run_mode
            self.jump(self.on_error)
            self.error_handle_mode = True
            self.session.events.suspend_all = True
        else:
            self.error_handle_mode = False
            self.set_pointer(False)
            raise e

    ###########################################################################
    # jumps

    def set_pointer(self, new_runmode, pos=None):
        """Set program pointer to the given codestream and position."""
        self.run_mode = new_runmode
        # events are active in run mode
        self.session.events.set_active(new_runmode)
        # keep the sound engine on to avoid delays in run mode
        self.session.sound.persist(new_runmode)
        # suppress cassette messages in run mode
        self.session.devices.devices['CAS1:'].quiet(new_runmode)
        codestream = self.get_codestream()
        if pos is not None:
            # jump to position, if given
            codestream.seek(pos)
        else:
            # position at end - don't execute anything unless we jump
            codestream.seek(0, 2)

    def get_codestream(self):
        """Get the current codestream."""
        return self.program_code if self.run_mode else self.session.direct_line

    def jump(self, jumpnum, err=error.UNDEFINED_LINE_NUMBER):
        """Execute jump for a GOTO or RUN instruction."""
        if jumpnum is None:
            self.set_pointer(True, 0)
        else:
            try:
                # jump to target
                self.set_pointer(True, self.session.program.line_numbers[jumpnum])
            except KeyError:
                raise error.RunError(err)

    def jump_gosub(self, jumpnum, handler=None):
        """Execute jump for a GOSUB."""
        # set return position
        self.gosub_stack.append((self.get_codestream().tell(), self.run_mode, handler))
        self.jump(jumpnum)

    def jump_return(self, jumpnum):
        """Execute jump for a RETURN."""
        try:
            pos, orig_runmode, handler = self.gosub_stack.pop()
        except IndexError:
            raise error.RunError(error.RETURN_WITHOUT_GOSUB)
        # returning from ON (event) GOSUB, re-enable event
        if handler:
            # if stopped explicitly using STOP, we wouldn't have got here; it STOP is run  inside the trap, no effect. OFF in trap: event off.
            handler.stopped = False
        if jumpnum is None:
            # go back to position of GOSUB
            self.set_pointer(orig_runmode, pos)
        else:
            # jump to specified line number
            self.jump(jumpnum)

    ###########################################################################
    # loops

    def loop_init(self, ins, forpos, nextpos, varname, start, stop, step):
        """Initialise a FOR loop."""
        # set start to start-step, then iterate - slower on init but allows for faster iterate
        self.session.scalars.set(varname, start.clone().isub(step))
        # obtain a view of the loop variable
        counter_view = self.session.scalars.view(varname)
        self.for_stack.append(
            (counter_view, stop, step, step.sign(), forpos, nextpos,))
        ins.seek(nextpos)

    def loop_iterate(self, ins, pos):
        """Iterate a loop (NEXT)."""
        # find the matching NEXT record
        num = len(self.for_stack)
        for depth in range(num):
            counter_view, stop, step, sgn, forpos, nextpos = self.for_stack[-depth-1]
            if pos == nextpos:
                # only drop NEXT record if we've found a matching one
                self.for_stack = self.for_stack[:len(self.for_stack)-depth]
                break
        else:
            raise error.RunError(error.NEXT_WITHOUT_FOR)
        # increment counter
        counter_view.iadd(step)
        # check condition
        loop_ends = counter_view.gt(stop) if sgn > 0 else stop.gt(counter_view)
        if loop_ends:
            self.for_stack.pop()
        else:
            ins.seek(forpos)
        return not loop_ends

    ###########################################################################
    # DATA utilities

    def restore(self, datanum=-1):
        """Reset data pointer (RESTORE) """
        try:
            self.data_pos = 0 if datanum == -1 else self.session.program.line_numbers[datanum]
        except KeyError:
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)

    def read_entry(self):
        """READ a unit of DATA."""
        current = self.program_code.tell()
        self.program_code.seek(self.data_pos)
        if self.program_code.peek() in tk.END_STATEMENT:
            # initialise - find first DATA
            self.program_code.skip_to((tk.DATA,))
        if self.program_code.read(1) not in (tk.DATA, ','):
            raise error.RunError(error.OUT_OF_DATA)
        vals, word, literal = '', '', False
        while True:
            # read next char; omit leading whitespace
            if not literal and vals == '':
                c = self.program_code.skip_blank()
            else:
                c = self.program_code.peek()
            # parse char
            if c == '' or (not literal and c == ',') or (c in tk.END_LINE or (not literal and c in tk.END_STATEMENT)):
                break
            elif c == '"':
                self.program_code.read(1)
                literal = not literal
                if (not literal) and (self.program_code.skip_blank() not in (tk.END_STATEMENT + (',',))):
                    raise error.RunError(error.STX)
            else:
                self.program_code.read(1)
                if literal:
                    vals += c
                else:
                    word += c
                # omit trailing whitespace
                if c not in self.program_code.blanks:
                    vals += word
                    word = ''
        self.data_pos = self.program_code.tell()
        self.program_code.seek(current)
        return vals

    ###########################################################################
    # expression parser

    def parse_value(self, ins, sigil=None, allow_empty=False):
        """Read a value of required type and return as Python value, or None if empty."""
        expr = self.parse_expression(ins, allow_empty)
        if expr is not None:
            # this will force into the requested type; e.g. Integers may overflow
            return values.to_type(sigil, expr).to_value()
        return None

    def parse_bracket(self, ins):
        """Compute the value of the bracketed expression."""
        ins.require_read(('(',))
        # we'll get a Syntax error, not a Missing operand, if we close with )
        val = self.parse_expression(ins)
        ins.require_read((')',))
        return val

    def parse_temporary_string(self, ins, allow_empty=False):
        """Parse an expression and return as Python value. Store strings in a temporary."""
        # if allow_empty, a missing value is returned as an empty string
        with self.temp_string:
            expr = self.parse_expression(ins, allow_empty)
            if expr:
                return values.pass_string(expr).to_value()
            return self.values.new_string()

    def parse_literal(self, ins):
        """Compute the value of the literal at the current code pointer."""
        d = ins.skip_blank()
        # string literal
        if d == '"':
            ins.read(1)
            if ins == self.session.program.bytecode:
                address = ins.tell() + self.session.memory.code_start
            else:
                address = None
            output = bytearray()
            # while tokenised numbers inside a string literal will be printed as tokenised numbers, they don't actually execute as such:
            # a \00 character, even if inside a tokenised number, will break a string literal (and make the parser expect a
            # line number afterwards, etc. We follow this.
            d = ins.read(1)
            while d not in tk.END_LINE + ('"',):
                output += d
                d = ins.read(1)
            if d == '\0':
                ins.seek(-1, 1)
            # if this is a program, create a string pointer to code space
            # don't reserve space in string memory
            return self.values.from_str_at(output, address)
        # number literals as ASCII are accepted in tokenised streams. only if they start with a figure (not & or .)
        # this happens e.g. after non-keywords like AS. They are not acceptable as line numbers.
        elif d in string.digits:
            return self.values.from_token(self.session.tokeniser.tokenise_number(ins))
        # number literals
        elif d in tk.NUMBER:
            return self.values.from_token(ins.read_token())
        # gw-basic allows adding line numbers to numbers
        elif d == tk.T_UINT:
            return self.values.new_integer().from_int(self.statements.parse_jumpnum(ins), unsigned=True)
        else:
            raise error.RunError(error.STX)

    def parse_variable(self, ins):
        """Helper function: parse a scalar or array element."""
        name = self.parse_scalar(ins)
        indices = []
        if ins.skip_blank_read_if(('[', '(')):
            # it's an array, read indices
            while True:
                indices.append(values.to_int(self.parse_expression(ins)))
                if not ins.skip_blank_read_if((',',)):
                    break
            ins.require_read((']', ')'))
        return name, indices

    def parse_scalar(self, ins, allow_empty=False):
        """Get scalar part of variable name from token stream."""
        # append type specifier
        name = self.session.memory.complete_name(ins.read_name(allow_empty))
        # return None for empty names (only happens with allow_empty)
        if not name:
            return None
        # only the first 40 chars are relevant in GW-BASIC, rest is discarded
        if len(name) > 41:
            name = name[:40]+name[-1]
        return name.upper()

    def parse_file_number(self, ins, file_mode='IOAR'):
        """Helper function: parse a file number and retrieve the file object."""
        screen = None
        if ins.skip_blank_read_if(('#',)):
            number = values.to_int(self.parse_expression(ins))
            error.range_check(0, 255, number)
            screen = self.session.files.get(number, file_mode)
            ins.require_read((',',))
        return screen

    def parse_file_number_opthash(self, ins):
        """Helper function: parse a file number, with optional hash."""
        ins.skip_blank_read_if(('#',))
        number = values.to_int(self.parse_expression(ins))
        error.range_check(0, 255, number)
        return number

    def parse_expression(self, ins, allow_empty=False, empty_err=error.MISSING_OPERAND):
        """Compute the value of the expression at the current code pointer."""
        stack = deque()
        units = deque()
        d = ''
        # see https://en.wikipedia.org/wiki/Shunting-yard_algorithm
        while True:
            last = d
            d = ins.skip_blank()
            # two-byte function tokens
            if d in tk.TWOBYTE:
                d = ins.peek(n=2)
            if d == tk.NOT and not (last in op.OPERATORS or last == ''):
                # unary NOT ends expression except after another operator or at start
                break
            elif d in op.OPERATORS:
                ins.read(len(d))
                # get combined operators such as >=
                if d in op.COMBINABLE:
                    nxt = ins.skip_blank()
                    if nxt in op.COMBINABLE:
                        d += ins.read(len(nxt))
                if last in op.OPERATORS or last == '' or d == tk.NOT:
                    # also if last is ( but that leads to recursive call and last == ''
                    nargs = 1
                    # zero operands for a binary operator is always syntax error
                    # because it will be seen as an illegal unary
                    if d not in op.UNARY:
                        raise error.RunError(error.STX)
                else:
                    nargs = 2
                    if d not in op.OPERATORS:
                        # illegal combined ops like == raise syntax error
                        raise error.RunError(error.STX)
                    self._evaluate_stack(stack, units, op.PRECEDENCE[d], error.STX)
                stack.append((d, nargs))
            elif not (last in op.OPERATORS or last == ''):
                # repeated unit ends expression
                # repeated literals or variables or non-keywords like 'AS'
                break
            elif d == '(':
                units.append(self.parse_bracket(ins))
            elif d and d in string.ascii_letters:
                # variable name
                name, indices = self.parse_variable(ins)
                units.append(self.session.memory.get_variable(name, indices))
            elif d in self.functions.functions:
                # apply functions
                ins.read(len(d))
                units.append(self.functions.functions[d](ins))
            elif d in tk.END_STATEMENT:
                break
            elif d in tk.END_EXPRESSION:
                # missing operand inside brackets or before comma is syntax error
                empty_err = error.STX
                break
            else:
                # literal
                units.append(self.parse_literal(ins))
        # empty expression is a syntax error (inside brackets)
        # or Missing Operand (in an assignment)
        # or not an error (in print and many functions)
        if units or stack:
            self._evaluate_stack(stack, units, 0, empty_err)
            return units[0]
        elif allow_empty:
            return None
        else:
            raise error.RunError(empty_err)

    def _evaluate_stack(self, stack, units, precedence, missing_err):
        """Drain evaluation stack until an operator of low precedence on top."""
        while stack:
            if precedence > op.PRECEDENCE[stack[-1][0]]:
                break
            oper, narity = stack.pop()
            try:
                right = units.pop()
                if narity == 1:
                    units.append(op.UNARY[oper](right))
                else:
                    left = units.pop()
                    units.append(op.BINARY[oper](left, right))
            except IndexError:
                # insufficient operators, error depends on context
                raise error.RunError(missing_err)

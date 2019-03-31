"""
PC-BASIC test_console
Tests for console

(c) 2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import unittest
import os
import shutil
import platform
from io import BytesIO

from pcbasic import Session


_LIPSUM = (
    b'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt '
    b'ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco '
    b'laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in '
    b'voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat '
    b'cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.'
)


class _TestCase(unittest.TestCase):
    """Base class for test cases."""

    tag = None

    def __init__(self, *args, **kwargs):
        """Define output dir name."""
        unittest.TestCase.__init__(self, *args, **kwargs)
        here = os.path.dirname(os.path.abspath(__file__))
        self._dir = os.path.join(here, u'output', self.tag)

    def setUp(self):
        """Ensure output directory exists and is empty."""
        try:
            shutil.rmtree(self._dir)
        except EnvironmentError:
            pass
        os.mkdir(self._dir)

    def _output_path(self, *names):
        """Output file name."""
        return os.path.join(self._dir, *names)

    def _get_text_stripped(self, s):
        """Get screen text stripped of trailing spaces."""
        return [_row.rstrip() for _row in s.get_text()]


class ConsoleTest(_TestCase):
    """Console tests."""

    tag = u'console'

    def test_control_keys(self):
        """Test special keys in console."""
        with Session() as s:
            s.execute(b'cls:print "%s"' % (_LIPSUM[:200],))
            # home
            s.press_keys(u'\0\x47')
            s.press_keys(u'1')
            # ctrl + right
            s.press_keys(u'\0\x74\0\x74')
            s.press_keys(u'2')
            # ctrl + left
            s.press_keys(u'\0\x73\0\x73')
            s.press_keys(u'3')
            # right
            s.press_keys(u'\0\x4d\0\x4d')
            s.press_keys(u'4')
            # left
            s.press_keys(u'\0\x4b\0\x4b')
            s.press_keys(u'5')
            # ctrl + right
            s.press_keys(u'\0\x74\0\x74')
            s.press_keys(u'6')
            # backspace
            s.press_keys(u'\b')
            s.press_keys(u'7')
            # ctrl + right
            s.press_keys(u'\0\x74\0\x74')
            s.press_keys(u'8')
            # ctrl + end
            s.press_keys(u'\0\x75')
            s.press_keys(u'9')
            # down
            s.press_keys(u'\0\x50\0\x50\0\x50')
            # up
            s.press_keys(u'\0\x48')
            s.press_keys(u'system\r')
            s.interact()
        assert self._get_text_stripped(s) == [
            b'1orem 3p54m 2olor 7t amet, 89',
            b'Ok\xff',
            b'                             system'
        ] + [b''] * 22

    def test_control_keys_2(self):
        """Test special keys in console."""
        with Session() as s:
            # bel
            s.press_keys(u'1\a2')
            # tab
            s.press_keys(u'3\t4')
            # lf
            s.press_keys(u'5\n6')
            # down, down
            s.press_keys(u'\0\x50\0\x50')
            # esc
            s.press_keys(u'7\x1b8')
            # down, system, enter
            s.press_keys(u'\0\x50system\r')
            s.interact()
        assert self._get_text_stripped(s) == [
            b'Ok\xff', b'123     45', b'6', b'', b'8', b' system',
        ] + [b''] * 19

    def test_control_keys_3(self):
        """Test special keys in console."""
        with Session() as s:
            s.execute(b'cls:print "%s"' % (_LIPSUM[:200],))
            # home
            s.press_keys(u'\0\x47')
            # del
            s.press_keys(u'\0\x53')
            # ins
            s.press_keys(u'\0\x52')
            s.press_keys(u'1')
            # down, system, enter
            s.press_keys(u'\0\x50\0\x50\0\x50\0\x50system\r')
            s.interact()
        assert self._get_text_stripped(s) == [
            b'1orem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor i',
            b'ncididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostru',
            b'd exercitation ullamco laboris nisi ut a',
            b'Ok\xff',
            b' system',
        ] + [b''] * 20

    def test_end(self):
        """Test end key in console."""
        with Session() as s:
            s.execute(b'cls:print "%s"' % (_LIPSUM[:200],))
            # ctrl + home
            s.press_keys(u'\0\x77')
            s.press_keys(u'system\r')
            s.interact()
        assert self._get_text_stripped(s) == [b'system'] + [b''] * 24

    def test_control_home(self):
        """Test ctrl-home in console."""
        with Session() as s:
            s.execute(b'cls:print "%s"' % (_LIPSUM[:200],))
            # home
            s.press_keys(u'\0\x47')
            # end
            s.press_keys(u'\0\x4f')
            # down, esc, system, enter
            s.press_keys(u'\0\x50\x1bsystem\r')
            s.interact()
        assert self._get_text_stripped(s) == [
            b'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor i',
            b'ncididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostru',
            b'd exercitation ullamco laboris nisi ut a',
            b'system'
        ] + [b''] * 21

    def test_control_printscreen(self):
        """Test ctrl+printscreen in console."""
        with Session(devices={'lpt1:': 'FILE:'+self._output_path(u'printscr.txt')}) as s:
            s.execute(b'cls:print "%s"' % (_LIPSUM[:200],))
            # ctrl + prtscr
            s.press_keys(u'\0\x72')
            # down, system, enter
            s.press_keys(u'\0\x50\0\x50\0\x50\0\x50system\r')
            s.interact()
        with open(self._output_path(u'printscr.txt'), 'rb') as f:
            assert f.read() == b'system\r\n'

    def test_control_c(self):
        """Test ctrl-home in console."""
        with Session() as s:
            # ctrl+c
            s.press_keys(u'\x03')
            s.press_keys(u'system\r')
            s.interact()
        assert self._get_text_stripped(s) == [b'Ok\xff', b'', b'system'] + [b'']*22

    def test_print_control(self):
        """Test printing control chars."""
        with Session() as s:
            s.execute(b'print chr$(7) "1" chr$(9) "2" chr$(&h1c) "3" chr$(&h1d) "4"')
            s.execute(b'print chr$(7)+"1"+chr$(9)+"2"+chr$(&h1c)+"3"+chr$(&h1d)+"4"')
        assert self._get_text_stripped(s) == [b'1       2 4', b'1       2 4'] + [b''] * 23

    def test_print_control_2(self):
        """Test printing control chars."""
        with Session() as s:
            s.execute(b'print "  1" chr$(&h1f) chr$(&h1f) "2" chr$(&h1e) "3" chr$(&h0b) "4"')
        assert self._get_text_stripped(s) == [b'4 1', b'    3', b'   2'] +[b''] * 22

    def test_print_control_3(self):
        """Test printing control chars."""
        with Session() as s:
            s.execute(b'print "  1" chr$(&h1f) chr$(&h1f) "2" chr$(&h1e) "3" chr$(&h0c) "4"')
        assert self._get_text_stripped(s) == [b'4'] + [b''] * 24

    def test_input_wrapping_line(self):
        """Test ctrl-home in console."""
        with Session() as s:
            s.press_keys(u'1\r')
            s.execute(b'cls:print "%s"' % (_LIPSUM[:200],))
            s.execute(b'locate 1,1: input a$')
            assert s.get_variable('a$') == b'1'
            assert self._get_text_stripped(s)[0] == (
                b'? 1em ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor i'
            )

    def test_close_stream(self):
        """Test ctrl-home in console."""
        with open(self._output_path(u'input.txt'), 'wb') as f:
            f.write(b'?1\r')
        input_stream = open(self._output_path(u'input.txt'), 'rb')
        with Session(input_streams=input_stream) as s:
            s.interact()
        assert self._get_text_stripped(s) == [b'Ok\xff', b'?1', b' 1', 'Ok\xff'] + [b''] * 21


if __name__ == '__main__':
    unittest.main()
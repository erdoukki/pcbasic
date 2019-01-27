"""
PC-BASIC - display.cursor
Cursor operations

(c) 2013--2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ..base import signals


class Cursor(object):
    """Manage the cursor."""

    def __init__(self, queues, mode):
        """Initialise the cursor."""
        self._queues = queues
        self._mode = mode
        self._colourmap = None
        # are we in parse mode? invisible unless visible_run is True
        self._default_visible = True
        # cursor visible in parse mode? user override
        self._visible_run = False
        # actually visible at present
        self._visible = False
        # cursor shape
        self._from_line = 0
        self._to_line = 0
        self._width = self._mode.font_width
        self._height = self._mode.font_height
        self._fore_attr = None
        self._row, self._col = 1, 1

    def init_mode(self, mode, attr, colourmap):
        """Change the cursor for a new screen mode."""
        self._mode = mode
        self._height = mode.font_height
        self._colourmap = colourmap
        self._visible = False
        # set the cursor position and attribute
        self.move(1, 1, attr, new_width=1)
        # cursor width starts out as single char
        self.set_default_shape(True)
        self.reset_visibility()

    def set_attr(self, new_attr):
        """Set the text cursor attribute and submit."""
        self.move(self._row, self._col, new_attr, None)

    def show(self, do_show):
        """Force cursor to be visible/invisible."""
        self._visible = do_show
        if do_show:
            # update position and looks
            self._queues.video.put(signals.Event(
                signals.VIDEO_MOVE_CURSOR, (self._row, self._col, self._fore_attr, self._width)
            ))
        # show or hide the cursor
        self._queues.video.put(signals.Event(
            signals.VIDEO_SHOW_CURSOR, (do_show, self._mode.is_text_mode)
        ))

    def move(self, new_row, new_column, new_attr=None, new_width=None):
        """Move the cursor and submit."""
        if new_attr:
            fore, _, _, _ = self._colourmap.split_attr(new_attr)
        else:
            fore = self._fore_attr
        if not new_width:
            new_width = self._width
        else:
            new_width = new_width * self._mode.font_width
        if (
                (new_row, new_column) == (self._row, self._col)
                and fore == self._fore_attr and new_width == self._width
            ):
            return
        # only submit move signal if visible (so that we see it in the right place)
        # or if the row changes (so that row-based cli interface can keep up with current row
        if self._visible or new_row != self._row:
            self._queues.video.put(signals.Event(
                signals.VIDEO_MOVE_CURSOR, (new_row, new_column, fore, new_width)
            ))
        self._row, self._col = new_row, new_column
        self._fore_attr = fore
        self._width = new_width

    def set_visibility(self, visible_run):
        """Set cursor visibility when a program is being run."""
        self._visible_run = visible_run
        self.reset_visibility()

    def set_default_visible(self, on):
        """Set default visibility (parse mode)."""
        self._default_visible = on

    def reset_visibility(self):
        """Set cursor visibility to its default state."""
        # visible if in interactive mode and invisible when a program is being run
        visible = self._default_visible
        # unless forced to be visible
        # in graphics mode, we can't force the cursor to be visible on execute.
        if self._mode.is_text_mode:
            visible = visible or self._visible_run
        if self._visible != visible:
            self.show(visible)

    @property
    def shape(self):
        """Cursor shape (from, to)."""
        return self._from_line, self._to_line

    def set_shape(self, from_line, to_line):
        """Set the cursor shape."""
        # odd treatment of cursors on EGA/VGA machines (14-pixel and up),
        # presumably for backward compatibility
        # the following algorithm is based on DOSBox source int10_char.cpp
        #     INT10_SetCursorShape(Bit8u first,Bit8u last)
        if self._height > 9:
            max_line = self._height - 1
            if from_line & 0xe0 == 0 and to_line & 0xe0 == 0:
                if (to_line < from_line):
                    # invisible only if to_line is zero and to_line < from_line
                    if to_line != 0:
                        # block shape from *to_line* to end
                        from_line = to_line
                        to_line = max_line
                elif ((from_line | to_line) >= max_line or
                            to_line != max_line-1 or from_line != max_line):
                    if to_line > 3:
                        if from_line+2 < to_line:
                            if from_line > 2:
                                from_line = (max_line+1) // 2
                            to_line = max_line
                        else:
                            from_line = from_line - to_line + max_line
                            to_line = max_line
                            if max_line > 0xc:
                                from_line -= 1
                                to_line -= 1
        self._from_line = max(0, min(from_line, self._height-1))
        self._to_line = max(0, min(to_line, self._height-1))
        self._queues.video.put(signals.Event(
            signals.VIDEO_SET_CURSOR_SHAPE, (self._from_line, self._to_line))
        )

    def set_default_shape(self, overwrite_shape):
        """Set the cursor to one of two default shapes."""
        if overwrite_shape:
            # most modes have cursor on last line
            self.set_shape(*self._mode.cursor_shape)
        else:
            # half-block cursor for insert
            self.set_shape(self._height//2, self._height-1)

    def rebuild(self):
        """Rebuild the cursor on resume."""
        if self._visible:
            self._queues.video.put(signals.Event(
                signals.VIDEO_SET_CURSOR_SHAPE, (self._from_line, self._to_line)
            ))
            self._queues.video.put(signals.Event(
                signals.VIDEO_MOVE_CURSOR, (self._row, self._col, self._fore_attr, self._width)
            ))
        self._queues.video.put(signals.Event(
            signals.VIDEO_SHOW_CURSOR, (self._visible, self._mode.is_text_mode)
        ))
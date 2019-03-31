# -*- coding: utf-8 -*-

"""
PC-BASIC test.codepage
codepage functionality tests

(c) 2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import unittest
import os
import shutil
from io import open

from pcbasic import Session, run
from pcbasic.data import read_codepage

HERE = os.path.dirname(os.path.abspath(__file__))


class CodepageTest(unittest.TestCase):
    """Unit tests for Session."""

    def setUp(self):
        """Ensure output directory exists."""
        try:
            os.mkdir(os.path.join(HERE, u'output', u'codepage'))
        except EnvironmentError:
            pass
        # create directory to mount
        self._test_dir = os.path.join(HERE, u'output', u'codepage', u'test_dir')
        try:
            shutil.rmtree(self._test_dir)
        except EnvironmentError:
            pass
        os.mkdir(self._test_dir)

    def _output_path(self, *name):
        """Test output file name."""
        return os.path.join(self._test_dir, *name)

    def test_nobox(self):
        """Test no box protection."""
        cp_936 = read_codepage('936')
        with Session(
                codepage=cp_936, box_protect=False, textfile_encoding='utf-8',
                devices={'c': self._test_dir},
            ) as s:
            s.execute('open "c:boxtest.txt" for output as 1')
            s.execute('PRINT#1, CHR$(218);STRING$(10,CHR$(196));CHR$(191)')
            # to screen
            s.execute('PRINT CHR$(218);STRING$(10,CHR$(196));CHR$(191)')
            # bytes text
            # bytes text
            output_bytes = [_row.strip() for _row in s.get_text()]
            # unicode text
            output_unicode = [_row.strip() for _row in s.get_text(as_type=type(u''))]
        with open(self._output_path('BOXTEST.TXT'), 'r') as f:
            assert f.read() == u'\ufeff谀哪哪哪哪目\n\x1a'
        assert output_bytes[0] == b'\xda\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xbf'
        assert output_unicode[0] == u'谀哪哪哪哪目'

    def test_box(self):
        """Test box protection."""
        cp_936 = read_codepage('936')
        with Session(
                codepage=cp_936, box_protect=True, textfile_encoding='utf-8',
                devices={'c': self._test_dir},
            ) as s:
            # to file
            s.execute('open "c:boxtest.txt" for output as 1')
            s.execute('PRINT#1, CHR$(218);STRING$(10,CHR$(196));CHR$(191)')
            # to screen
            s.execute('PRINT CHR$(218);STRING$(10,CHR$(196));CHR$(191)')
            # bytes text
            output_bytes = [_row.strip() for _row in s.get_text()]
            # unicode text
            output_unicode = [_row.strip() for _row in s.get_text(as_type=type(u''))]
        with open(self._output_path('BOXTEST.TXT'), 'r') as f:
            assert f.read() == u'\ufeff┌──────────┐\n\x1a'
        assert output_bytes[0] == b'\xda\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xbf'
        assert output_unicode[0] == u'┌──────────┐'

    def test_box2(self):
        """Test box protection cases."""
        cp_936 = read_codepage('936')
        with Session(codepage=cp_936, box_protect=True) as s:
            s.execute('a$= "+"+STRING$(3,CHR$(196))+"+"')
            s.execute('b$= "+"+STRING$(2,CHR$(196))+"+"')
            s.execute('c$= "+"+STRING$(1,CHR$(196))+"+"')
            s.execute('d$= "+"+CHR$(196)+chr$(196)+chr$(190)+chr$(196)+"+"')
            assert s.get_variable('a$') == b'+\xc4\xc4\xc4+'
            assert s.get_variable('b$') == b'+\xc4\xc4+'
            assert s.get_variable('c$') == b'+\xc4+'
            assert s.get_variable('d$') == b'+\xc4\xc4\xbe\xc4+'
            # three consecutive lines are protected
            assert s.get_variable('a$', as_type=type(u'')) == u'+\u2500\u2500\u2500+'
            # two consecutive lines are not
            assert s.get_variable('b$', as_type=type(u'')) == u'+\u54ea+'
            # single lead byte is shown as box drawing
            assert s.get_variable('c$', as_type=type(u'')) == u'+\u2500+'
            # two box lines followed by a non-box lead & trail byte - not protected
            assert s.get_variable('d$', as_type=type(u'')) == u'+\u54ea\u7078+'

    def test_hello(self):
        """Hello world in 9 codepages."""
        hello = {
            # contains \u064b which is not in 720
            #'720': u'أهلاً بالعالم',
            '720': u'أهلا بالعالم',
            '737': u'Γεια σου κόσμε',
            '862': u'שלום עולם',
            '866': u'Здравствуй, мир',
            # combining graphemes \u0e27\u0e31 \u0e14\u0e35 are in codepage as separate chars
            # so converting to bytes fails
            #'874': u'สวัสดีโลก',
            #'874': u'\u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35\u0e42\u0e25\u0e01',
            '932': u'こんにちは、 世界',
            '936': u'你好世界',
            '949': u'반갑다 세상아',
            'viscii': u'Xin chào thế giới',
        }
        # note that we're making a round-trip conversion unicode -> codepage -> unicode
        # this doesn't always work
        for cp, hi in hello.items():
            with open(self._output_path(hi), 'w') as f:
                f.write(hi)
            cp_dict = read_codepage(cp)
            with Session(
                    codepage=cp_dict, textfile_encoding='utf-8', devices={'c': self._test_dir},
                ) as s:
                s.execute(u'cls:print "{}"'.format(hi))

                #TODO: (api) should have an errors= option in convert?
                #TODO: (codepages) only perform grapheme clustering if the codepage has actual clusters in code points? (but: non-canonical combinations) override clustering if clustering elements in codepage?
                #cp_inv = {_v: _k for _k, _v in cp_dict.items()}
                #print repr(hi), repr(s.convert(hi, to_type=type(b''))), repr([cp_inv[x] for x in hi])

                s.execute(u'open "c:{}" for input as 1'.format(hi))
                s.execute('line input#1, a$')
                assert s.get_variable('a$', as_type=type(u'')) == hi
                output_unicode = [_row.strip() for _row in s.get_text(as_type=type(u''))]
                assert output_unicode[0] == hi

    def test_missing(self):
        """Test codepage with missing codepoints."""
        cp = {b'\xff': u'B'}
        with Session(codepage=cp) as s:
            s.execute('a$ = "abcde" + chr$(255)')
            assert s.get_variable('a$') == b'abcde\xff'
            assert s.get_variable('a$', as_type=type(u'')) == u'\0\0\0\0\0B'

    def test_non_nfc(self):
        """Test conversion of non-NFC sequences."""
        with Session() as s:
            # a-acute in NFD
            s.execute(u'a$ = "a\u0301"')
            # codepage 437 for a-acute
            assert s.get_variable('a$') == b'\xa0'


##############################################################################

from io import StringIO
import pickle
from pcbasic.compat import copyreg

from pcbasic.basic.codepage import InputStreamWrapper, OutputStreamWrapper
from pcbasic.basic.codepage import Codepage
#from pcbasic import state


def unpickle_stringio(buffer, pos):
    f = StringIO(buffer)
    f.seek(pos)
    return f

def pickle_stringio(f):
    return unpickle_stringio, (f.getvalue(), f.tell())

copyreg.pickle(StringIO, pickle_stringio)


class StreamWrapperTest(unittest.TestCase):
    """Unit tests for split_graphemes."""

    def test_read(self):
        """Test InputStreamWrapper.read()."""
        # unicode stream
        stream = StringIO(u'£abcde£')
        # use default codepage 437
        wrapper = InputStreamWrapper(stream, Codepage())
        # read codepage bytes
        assert wrapper.read(1) == b'\x9c'
        assert wrapper.read(1) == b'a'
        assert wrapper.read() == b'bcde\x9c'

    def test_write(self):
        """Test OutputStreamWrapper.write()."""
        stream = StringIO()
        wrapper = OutputStreamWrapper(stream, Codepage())
        wrapper.write(b'\x9cabcde\x9c')
        assert stream.getvalue() == u'£abcde£'

    def test_pickle(self):
        """Wrapped streams must be picklable."""
        # unicode stream
        stream = StringIO(u'£abcde£')
        # use default codepage 437
        wrapper = InputStreamWrapper(stream, Codepage())
        wrapper.read(2)
        pstr = pickle.dumps(wrapper)
        wrapper2 = pickle.loads(pstr)
        assert wrapper2.read() == b'bcde\x9c'


if __name__ == '__main__':
    unittest.main()
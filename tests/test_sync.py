import imaplib
from unittest.mock import patch, ANY

from mailur import parse


def test_binary_msg():
    assert parse.binary_msg('Ответ: 42').as_bytes() == '\r\n'.join([
        'MIME-Version: 1.0',
        'Content-Transfer-Encoding: binary',
        'Content-Type: text/plain; charset="utf-8"',
        '',
        'Ответ: 42'
    ]).encode()

    assert parse.binary_msg('Ответ: 42').as_string() == '\r\n'.join([
        'MIME-Version: 1.0',
        'Content-Transfer-Encoding: base64',
        'Content-Type: text/plain; charset="utf-8"',
        '',
        '0J7RgtCy0LXRgjogNDI=\r\n'
    ])


def login_gmail():
    def uid(name, *a, **kw):
        responces = getattr(login_gmail, name.lower(), None)
        if responces:
            return responces.pop()
        return con.uid_origin(name, *a, **kw)

    con = imaplib.IMAP4('localhost', 143)
    con.login('test2*root', 'root')

    con.uid_origin = con.uid
    con.uid = uid
    return con


@patch('mailur.parse.login_gmail', login_gmail)
@patch('mailur.parse.USER', 'test1')
def test_gmail_fetch_and_parse():
    gm = parse.connect_gmail()
    assert gm.current_folder == b'All'

    dc = parse.connect()
    assert hasattr(dc, 'multiappend')
    assert hasattr(dc, 'setmetadata')
    assert hasattr(dc, 'getmetadata')
    parse.fetch_folder()
    parse.parse_folder()

    def gmail_uidnext():
        res = dc.getmetadata('gmail/uidnext/all')
        assert res == ('OK', [
            (b'All (/private/gmail/uidnext/all {12}', ANY),
            b')'
        ])
        return res[1][0][1]

    def mlr_uidnext():
        res = dc.getmetadata('mlr/uidnext')
        assert res == ('OK', [
            (b'All (/private/mlr/uidnext {1}', ANY),
            b')'
        ])
        return res[1][0][1]

    assert gmail_uidnext().endswith(b',1')
    assert dc.getmetadata('mlr/uidnext') == ('OK', [
        b'All (/private/mlr/uidnext NIL)'
    ])

    msg = parse.binary_msg('42').as_bytes()
    gm.append('All', None, None, msg)
    login_gmail.fetch = [('OK', [
        (
            b'1 (X-GM-MSGID 777 X-GM-LABELS ("\\\\Inbox") UID 4774 '
            b'INTERNALDATE "08-Jul-2017 09:08:30 +0000" FLAGS () '
            b'BODY[] {%d}' % len(msg),
            msg
        ),
        b')'
    ])]
    parse.fetch_folder()
    parse.parse_folder()
    assert gmail_uidnext().endswith(b',2')
    assert mlr_uidnext() == b'2'
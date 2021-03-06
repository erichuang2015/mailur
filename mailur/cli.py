"""Mailur CLI

Usage:
  mlr gmail <login> set <username> <password>
  mlr gmail <login> [--tag=<tag> --box=<box> --parse] [options]
  mlr parse <login> [<criteria>] [options]
  mlr threads <login> [<criteria>]
  mlr sync <login> [--timeout=<timeout>]
  mlr sync-flags <login> [--reverse]
  mlr clean-flags <login>
  mlr update-links <login>
  mlr update-metadata <login>
  mlr icons
  mlr web
  mlr lint [--ci]
  mlr test
  mlr -h | --help
  mlr --version

Options:
  -b <batch>    Batch size [default: 1000].
  -t <threads>  Amount of threads for thread pool [default: 2].
"""
import functools as ft
import pathlib
import sys
import time

from docopt import docopt

from gevent import joinall, sleep, spawn

from . import LockError, conf, gmail, local, log

root = pathlib.Path(__file__).parent.parent


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    args = docopt(__doc__, args, version='Mailur 0.3')
    try:
        process(args)
    except KeyboardInterrupt:
        raise SystemExit('^C')


def process(args):
    conf['USER'] = args['<login>']
    opts = {
        'batch': int(args.get('-b')),
        'threads': int(args.get('-t')),
    }
    if args['gmail'] and args['set']:
        gmail.save_credentials(args['<username>'], args['<password>'])
    elif args['gmail']:
        select_opts = dict(tag=args['--tag'], box=args['--box'])
        fetch_opts = dict(opts, **select_opts)
        fetch_opts = {k: v for k, v in fetch_opts.items() if v}

        gmail.fetch(**fetch_opts)
        if args['--parse']:
            local.parse(**opts)
    elif args['parse']:
        local.parse(args.get('<criteria>'), **opts)
    elif args['sync']:
        sync(int(args['--timeout']))
    elif args['sync-flags']:
        if args['--reverse']:
            local.sync_flags_to_src()
        else:
            local.sync_flags_to_all()
    elif args['clean-flags']:
        local.clean_flags()
    elif args['update-links']:
        local.update_links()
    elif args['update-metadata']:
        local.save_addrs()
        local.save_msgids()
        local.save_uid_pairs()
    elif args['threads']:
        with local.client() as con:
            local.update_threads(con, criteria=args.get('<criteria>'))
    elif args['icons']:
        icons()
    elif args['web']:
        web()
    elif args['test']:
        run('pytest -n2 -q --cov=mailur --cov-report=term-missing')
    elif args['lint']:
        ci = args['--ci'] and 1 or ''
        run('ci=%s bin/run-lint' % ci)
    else:
        raise SystemExit('Target not defined:\n%s' % args)


def retry(fn):
    @ft.wraps(fn)
    def inner(*a, **kw):
        while 1:
            try:
                fn(*a, **kw)
            except Exception as e:
                log.exception(e)
                sleep(10)
    return inner


def sync(timeout=1200):
    @retry
    def remote():
        def handler(res=None):
            try:
                gmail.fetch()
                local.parse()
            except LockError as e:
                log.warn(e)

        try:
            gmail.get_credentials()
        except ValueError:
            log.info('## no credentials for gmail')
            return

        handler()
        with gmail.client(tag='\\All') as con:
            con.idle(handler, timeout=timeout)

    @retry
    def flags():
        local.sync_flags_to_all()
        local.sync_flags(timeout=timeout)

    try:
        jobs = [spawn(remote), spawn(flags)]
        joinall(jobs, raise_error=True)
    except KeyboardInterrupt:
        time.sleep(1)


def web():
    from gevent.subprocess import run
    from gevent.pool import Pool

    def api():
        run('bin/run-web', shell=True)

    def webpack():
        run('which yarn && yarn run dev || npm run dev', shell=True)

    try:
        pool = Pool()
        pool.spawn(api)
        pool.spawn(webpack)
        pool.join()
    except KeyboardInterrupt:
        time.sleep(1)


def run(cmd):
    from sys import exit
    from subprocess import call

    check = 'which pytest'
    if call(check, cwd=root, shell=True):
        raise SystemExit(
            'Test dependencies must be installed.\n'
            '$ pip install -e .[test]'
        )

    cmd = 'sh -xc %r' % cmd
    exit(call(cmd, cwd=root, shell=True))


def icons():
    import json
    import bottle

    font = root / 'assets/font'
    sel = (font / 'selection.json').read_text()
    sel = json.loads(sel)
    icons = [
        (i['properties']['name'], '\\%s' % hex(i['properties']['code'])[2:])
        for i in sel['icons']
    ]
    tpl = str((font / 'icons.less.tpl').resolve())
    txt = bottle.template(
        tpl, icons=icons,
        template_settings={'syntax': '{% %} % {{ }}'}
    )
    f = font / 'icons.less'
    f.write_text(txt)
    print('%s updated' % f)


if __name__ == '__main__':
    main()

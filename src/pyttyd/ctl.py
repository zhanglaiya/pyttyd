import os
import sys
import asyncio
import argparse


import paramiko

from pyttyd.crud import get_conns, get_conn, create_conn
from pyttyd.common import encodingmap, default_encoding


def win_getwch():
    import msvcrt
    return msvcrt.getwch()


def posix_getwch():
    return sys.stdin.read(1)

if os.name == 'nt':
    getwch = win_getwch
elif os.name == 'posix':
    getwch = posix_getwch


class Table:

    def __init__(self, conns):
        self.conns = conns

    @staticmethod
    def get_len(s):
        le = 0
        for i in s:
            le += 1
            if u'\u4e00' <= i <= u'\u9fff':
                le += 1
        return le

    def show(self):
        rows = [['ID', '连接名称', '主机', '端口', '用户名', '密码', '创建时间', '更新时间']]

        for c in self.conns:
            rows.append([
                c.id,
                c.name,
                c.host,
                str(c.port),
                c.user,
                c.password,
                c.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                c.update_time.strftime('%Y-%m-%d %H:%M:%S'),
            ])
        max_lens = [max([self.get_len(j) for j in i]) for i in zip(*rows)]

        for r in rows:
            max_lens_c = max_lens[:]
            for i, c in enumerate(r):
                for cc in c:
                    if u'\u4e00' <= cc <= u'\u9fff':
                        max_lens_c[i] -= 1
            tpl = '  '.join(['{' + '{0}:<{1}'.format(i, j) + '}' for i, j in enumerate(max_lens_c)])
            print(tpl.format(*r))


class Terminal(paramiko.SSHClient):

    def __init__(self, conn, rows, cols):

        super(Terminal, self).__init__()

        self._rows = rows
        self._cols = cols

        self.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.connect(conn['host'], conn['port'], conn['user'], conn['password'])
        _, stdout, _ = self.exec_command('$SHELL -ilc "locale charmap"')
        charmap = stdout.read().decode().strip()
        stdout.close()
        self._encoding = encodingmap.get(charmap, default_encoding)

    async def join(self):
        with self.invoke_shell('xterm', self._cols, self._rows) as chan:
            # chan.setblocking(1)
            # await read_chan(websocket, chan)
            consumer_task = asyncio.create_task(self.read_chan(chan))
            producer_task = asyncio.create_task(self.read_sock(chan))
            done, pending = await asyncio.wait(
                [consumer_task, producer_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

    async def read_chan(self, chan):
        while not chan.closed:
            s = await asyncio.to_thread(chan.recv, 1024)
            s = s.decode(self._encoding)
            sys.stdout.write(s)
            sys.stdout.flush()


    async def read_sock(self, chan):
        spec = 0
        while not chan.closed:
            # s = sys.stdin.readline()
            s = await asyncio.to_thread(getwch)
            # s = msvcrt.getwch()
            if s == '\x00':
                if spec != 1:
                    spec = 1
            elif spec == 1:
                if s == 'H':  # 上
                    chan.send('\x1b[A')
                elif s == 'K':  # 左
                    chan.send('\x1b[D')
                elif s == 'M':  # 右
                    chan.send('\x1b[C')
                elif s == 'P':  # 下
                    chan.send('\x1b[B')
                else:
                    chan.send(s)
                spec = 0
            else:
                chan.send(s.encode(self._encoding))


def list_conn(args):
    conns = get_conns(q=args.q if args.q else None)
    table = Table(conns)
    table.show()


def new_conn(args):

    item = {}
    item['name'] = ('连接名称', args.name)
    item['host'] = ('主机', args.host)
    item['port'] = ('端口', args.port)
    item['user'] = ('用户名', args.user)
    item['password'] = ('密码', args.password)
    for k, v in item.items():
        if v[1] is None:
            item[k] = input(f'请输入{v[0]}: \n')
    print('id: ', create_conn(item))


async def conn_to(args):
    c = get_conn(args.id)
    size = os.get_terminal_size()
    os.system('stty -echo')
    with Terminal(c, size.lines, size.columns) as term:
        await term.join()
    os.system('stty echo')

def ctl():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', dest='show_v', action='store_true', help='查看版本')
    root_sub = parser.add_subparsers()
    list_parser = root_sub.add_parser(name='list', help='查看已有连接列表')
    list_parser.set_defaults(func=list_conn)
    list_parser.add_argument('-q', dest='q', required=False, help='查询关键字')

    new_parse = root_sub.add_parser(name='new', help='新建连接保存')
    new_parse.set_defaults(func=new_conn)
    new_parse.add_argument('--name', dest='name', required=False, help='连接名称')
    new_parse.add_argument('--host', dest='host', required=False, help='主机', )
    new_parse.add_argument('--port', dest='port', required=False, help='端口')
    new_parse.add_argument('--user', dest='user', required=False, help='用户名')
    new_parse.add_argument('--pass', dest='password', required=False, help='密码')

    conn_parse = root_sub.add_parser(name='conn', help='根据id连接建立ssh连接')
    conn_parse.set_defaults(func=conn_to)
    conn_parse.add_argument('id', help='连接id')
    args = parser.parse_args()
    if args.show_v:
        print('1.0.6')
    elif 'func' in args:
        if asyncio.iscoroutinefunction(args.func):
            asyncio.run(args.func(args))
        else:
            args.func(args)
    else:
        parser.print_help()

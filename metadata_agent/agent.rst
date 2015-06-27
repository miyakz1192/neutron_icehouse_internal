===========================================
metadata agentのagent.pyの動作
===========================================

class MetadataProxyHandler(object):
====================================

metadata proxy agentの処理の中核となるクラス。
クライアントからのHTTP要求から、以下のヘッダを取り出して、port情報を求める。port情報からinstance_idとtenant_idを求めて、nova metadataに渡す。::

        X-Forwarded-For
        X-Neutron-Network-ID
        X-Neutron-Router-ID

port情報を求める際、neutron-serverと通信を行うため、応答はちょっと遅いかもしれない。

def _get_neutron_client(self):
----------------------------------

neutronクライアントを作成して返す。


def __call__(self, req):
----------------------------

wsgiのメソッドチェインで呼ばれるメソッド？
_get_instance_and_tenant_idを呼び出して、instance_idとtenant_idを
得てself._proxy_request(instance_id, tenant_id, req)を呼び出す。

何か例外が発生した場合は、500番を返却してリクエストのリトライを
促すメッセージを返す。


def _get_router_networks(self, router_id):
-------------------------------------------------

@utils.cache_method_resultsでデコレートされているメソッド
routerが接続しているネットワークの一覧を返す(外部ネットワークを
除く)



def _get_ports_for_remote_address(self, remote_address, networks):
-------------------------------------------------------------------

@utils.cache_method_resultsでデコレートされたメソッド
引数で与えたnetworkで、remote_addressを持つportを返す
（通常は１つになるはず)


def _get_ports(self, remote_address, network_id=None, router_id=None):
-------------------------------------------------------------------

network_idまたは、router_idのportを得るメソッド


def _get_instance_and_tenant_id(self, req):
-----------------------------------------------

req(ヘッダ)からnetwork_idとrouter_idを取り出して、_get_portsを呼び出す。得たport情報のdevice_idとtenant_idを返す。


def _proxy_request(self, instance_id, tenant_id, req):
---------------------------------------------------------

HTTPヘッダを設定して、nova metadata serverに要求を投げる。
引数はinstance_idとtenant_id。


def _sign_instance_id(self, instance_id):
--------------------------------------------

instance_idにサインする。


class UnixDomainHttpProtocol(eventlet.wsgi.HttpProtocol):
=============================================================


def __init__(self, request, client_address, server):
--------------------------------------------------------

wsgi.HttpProtocolを初期化して終わり


class WorkerService(wsgi.WorkerService):
===============================================

def start(self):
------------------

service.ProcessLauncherから呼び出されるために、wsgi.WorkerServiceを継承して、startを実装している。中身は、applicationの起動を_service.pools.spawnで起動しているだけ。


class UnixDomainWSGIServer(wsgi.Server):
============================================


def start(self, application, file_socket, workers, backlog):
-----------------------------------------------------------------

サーバを起動している。詳細はちょっとわからんが大体以下のような感じ。

1. eventlet.listenでsocketを開いて待つ
2. workers < 1の場合、MetadataProxyHandlerをスレッドに割り当てる。この場合は、スレッドは１つ(=MetadataProxyHandler)
3. workers >= 1の場合、service.ProcessLauncherを使う。WorkerServiceを作って(実態はapplication=MetadataProxyHandler)、self._launcher.launch_service(self._server, workers=workers)で起動しているだけ。

ここのソースコードで、applicationはMetadataProxyHandlerのインスタンス。


def _run(self, application, socket):
----------------------------------------

wsgi serverを起動している。ソース見たほうが早いかも::


    def _run(self, application, socket):
        """Start a WSGI service in a new green thread."""
        logger = logging.getLogger('eventlet.wsgi.server')
        eventlet.wsgi.server(socket,
                             application,
                             custom_pool=self.pool,
                             protocol=UnixDomainHttpProtocol,
                             log=logging.WritableLogger(logger))

_runは、self.pool.spawnから呼び出される。applicationはMetadataProxyHandlerである。


class UnixDomainMetadataProxy(object):
===========================================


def __init__(self, conf):
---------------------------

ディレクトリ(cfg.CONF.metadata_proxy_socket)が存在する場合、unlinkを行う。存在しない場合は、ディレクトリを作成する。

def _init_state_reporting(self):
----------------------------------

state reportのためのデータの初期化を行う。
loopingcall.FixedIntervalLoopingCallを実行して、_report_stateメソッドを
定期的に実行するようにする。実行間隔はneutron.confのreport_interval。

def _report_state(self):
--------------------------

stateをレポートする。AttributeErrorが発生した場合は、
heartbeat(loopingcall.FixedIntervalLoopingCallオブジェクト)のstopメソッドを実行する。

def run(self):
-----------------

UnixDomainWSGIServerを実行する。handlerはMetadataProxyHandler。::


        server = UnixDomainWSGIServer('neutron-metadata-agent')
        server.start(MetadataProxyHandler(self.conf),
                     self.conf.metadata_proxy_socket,
                     workers=self.conf.metadata_workers,
                     backlog=self.conf.metadata_backlog)
        server.wait()



def main():
============

いろいろと設定を読み込んだあとに、UnixDomainMetadataProxyのrunを実行する。


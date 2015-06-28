===============================================
MeteringAgentの解析
===============================================

class MeteringPluginRpc(proxy.RpcProxy):
==========================================

MeteringAgentがMeteringPluginとRPC会話するために、MeteringAgentによって使われるクラス。
RPCのバージョンは以下::

  BASE_RPC_API_VERSION = '1.0'


def __init__(self, host):
---------------------------

初期化している。


def _get_sync_data_metering(self, context):
-----------------------------------------------

neutron-server(のMeteringPluginの)、get_sync_data_meteringをhost引数を与えて呼び出し、このmetering agentが動作しているrouterの一覧を得る((個々のルータ情報には、label_idとlabel_ruleの情報が含まれる)　


class MeteringAgent(MeteringPluginRpc, manager.Manager):
==========================================================

MeteringAgentの実体となるクラス

データ構造
-------------

以下の通り。

+-------------------------+----------------------------------+
|データ                   |説明                              | 
+=========================+==================================+ 
|self.conf                |neutron.confの設定項目object      |
+-------------------------+----------------------------------+
|self.root_helper         |root_helperが格納されている       |
+-------------------------+----------------------------------+
|self.context             |adminコンテキスト                 |
+-------------------------+----------------------------------+
|self.metering_info       |測定情報?初期値は{}               |
+-------------------------+----------------------------------+
|self.metering_loop       |定期タスク(実体： _metering_loop  |
+-------------------------+----------------------------------+
|self.last_report         |最後にレポートした時刻?初期値0    |
+-------------------------+----------------------------------+
|self.host                |自分が動作しているホスト          |
+-------------------------+----------------------------------+
|self.label_tenant_id     |label_idがkey,tenant_idがvalのdict|
+-------------------------+----------------------------------+
|self.routers             |router情報?初期値{}               |
+-------------------------+----------------------------------+
|self.metering_infos      |測定情報？初期値{}                |
+-------------------------+----------------------------------+
                             
def __init__(self, host, conf=None):
---------------------------------------

以下の内容で初期化

1. Driverのロード
2. adminコンテキストを生成してself.contextに格納
3. self._metering_loopをloopingcall.FixedIntervalLoopingCallを利用して起動
4. 計測のインターバルをconfから読み込み
5. 計測ループの開始(self.metering_loop.start,実体は_metering_loopメソッド)

def _load_drivers(self):
--------------------------

importutils.import_objectを使って、self.conf.driverに設定されているドライバを読み込む。

def _metering_notification(self):
------------------------------------

self.metering_infos.items()を列挙して、label_idごとに測定結果をAMQPにpushする。形式は以下の通り。::

            data = {'label_id': label_id,
                    'tenant_id': self.label_tenant_id.get(label_id),
                    'pkts': info['pkts'],
                    'bytes': info['bytes'],
                    'time': info['time'],
                    'first_update': info['first_update'],
                    'last_update': info['last_update'],
                    'host': self.host}


def _purge_metering_info(self):
-----------------------------------

測定情報リスト(self.metering_info)の各測定情報のlast_updateが、現在時刻+report_intervalを越えている場合、self.metering_infoから測定情報を削除する。

疑問点：削除の判定を行う条件の不等号が逆のような気がする。::

    def _purge_metering_info(self):
        ts = int(time.time())
        report_interval = self.conf.report_interval
        for label_id, info in self.metering_info.items():
            if info['last_update'] > ts + report_interval:
                del self.metering_info[label_id]











==============================================
metering rpcの解析
==============================================

class MeteringRpcCallbacks(object):
======================================

meteringプラグインが使用するagentからのRPCのコールバック。

def __init__(self, meter_plugin):
--------------------------------

self.meter_pluginにmeter_pluginを格納するだけ。

def create_rpc_dispatcher(self):
--------------------------------

PluginRpcDispatcherを返すだけ

def get_sync_data_metering(self, context, **kwargs):
-----------------------------------------------------

l3_agentプラグインがスケジューラ機能をサポートしていない場合は、すべてのラベルに関連づくルータの一覧を返す（個々のルータの情報にはlabel_idとlabel_ruleを含む)

スケジューラをサポートしている場合は、kwargsで指定されたhost上で動作しているルータ一覧を返す（個々のルータの情報にはlabel_idとlabel_ruleを含む)







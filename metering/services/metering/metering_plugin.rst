==================================================
MeteringPluginの解析
==================================================

class MeteringPlugin(metering_db.MeteringDbMixin):
====================================================

neutron-server側のMeteringPluginの実装。

def __init__(self):
-----------------------

初期化メソッド。
metering_rpc.MeteringRpcCallbacks(self)をself.callbacks変数に保持。
self.connにrpc.create_connectionでコネクションを作成して保持。

create_consumerでqueueをconsumeする準備を完了する。::

        self.conn.create_consumer(
            topics.METERING_PLUGIN,
            self.callbacks.create_rpc_dispatcher(),
            fanout=False)

topicsは、'q-metering-plugin'
self.conn.consume_in_thread()を実行し、consumeを開始する。

def create_metering_label(self, context, metering_label):
-----------------------------------------------------------

MeteringDbMixinの同名のメソッドを呼び出し、DBにMeteringLabelを登録する。
次にself.get_sync_data_meteringを呼び出し、すべてのMeteringLabelに関連するrouterの一覧を得る(個々のルータの情報には、MeteringLabelのIDとMeteringLabelRuleの情報が付加されている)。routerの一覧をdata変数に格納する。
次に、self.meter_rpc.add_metering_label(context, data)を呼び出し、各ルータをホストしているmetering agnetにラベル追加の通知を行う。

ちょっと疑問：追加したルールのラベルのtenant_idのルータだけに通知を絞れば効率的では？


def delete_metering_label(self, context, label_id):
--------------------------------------------------------

self.get_sync_data_metering(context, label_id)を呼び出し、削除対象のlabel_idに関連づくrouterの一覧を得る。それをdata変数に格納する。
次に、MeteringDbMixinの同名のメソッドを呼び出し、DBからMeteringLabelを削除する。
次に、self.meter_rpc.remove_metering_label(context, data)を呼び出し、agentに通知を行う

気づき：削除したlabel_idに関連するmetering agnet(ルータをホストしているnetwork nodeで動作している)に対してのみ通知を行っている。


def create_metering_label_rule(self, context, metering_label_rule):
------------------------------------------------------------------

MeteringDbMixinの同名のメソッドを呼び出し、DBにMeteringLabelRuleを追加する。

次に、self.get_sync_data_metering(context)を呼び出し、すべてのlabelに関連づく、すべてのルータ一覧を得る(個々のルータの情報にはlabel_idとlabel_ruleの情報が付加されている)。結果はdata変数に格納する。　

最後に、self.meter_rpc.update_metering_label_rules(context, data)を呼び出し、routerをホストしているnetwork nodeで動作しているmetering agentに通知を行う。


def delete_metering_label_rule(self, context, rule_id):
----------------------------------------------------------

MeteringDbMixinの同名のメソッドを呼び出し、DBからMeteringLabelRuleを削除する。

次に、self.get_sync_data_metering(context)を呼び出し、すべてのlabelに関連づく、すべてのルータ一覧を得る(個々のルータの情報にはlabel_idとlabel_ruleの情報が付加されている)。結果はdata変数に格納する。　

最後に、self.meter_rpc.update_metering_label_rules(context, data)を呼び出し、routerをホストしているnetwork nodeで動作しているmetering agentに通知を行う。


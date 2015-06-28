======================================================
MeteringAgentNotifyAPIの解析
======================================================

class MeteringAgentNotifyAPI(proxy.RpcProxy):
=================================================

neutron-serverのMeteringPluginがmetering agentにMeteringLabelやMeteringLabelRuleの更新を伝えるために使われるクラス。ベースのAPIバージョンは1.0らしい。::

  BASE_RPC_API_VERSION = '1.0'

def __init__(self, topic=topics.METERING_AGENT):
---------------------------------------------------

初期化メソッド。以下の処理を実行し、親クラスの初期化を呼び出している。::

    def __init__(self, topic=topics.METERING_AGENT):
        super(MeteringAgentNotifyAPI, self).__init__(
            topic=topic, default_version=self.BASE_RPC_API_VERSION)

topicは 'metering_agent'。


def _agent_notification(self, context, method, routers):
-------------------------------------------------------------

引数のroutersの個々のルータが、どのhostで動作しているのかを整理する。
具体的には、hostがkeyで、valueがrouterのリストであるdictを作る。dictを作ったあと、そのdictを列挙して、各metering agentに通知を行う。::

        for host, routers in l3_routers.iteritems():
            self.cast(context, self.make_msg(method, routers=routers),
                      topic='%s.%s' % (self.topic, host))

通知はcastで行う。各ホストのmetering agnetに対して、本メソッドに与えられたmethodを実行する。methodの引数は、そのホストで動作しているrouterのリストである。


def _notification_fanout(self, context, method, router_id):
---------------------------------------------------------------

fanout_castのラッパー。本メソッドの引数である、method,router_idをfanout_castに渡しているだけで、大したことはしていないので説明は割愛して、コードだけ乗っけておく。::


    def _notification_fanout(self, context, method, router_id):
        LOG.debug(_('Fanout notify metering agent at %(topic)s the message '
                    '%(method)s on router %(router_id)s'),
                  {'topic': self.topic,
                   'method': method,
                   'router_id': router_id})
        self.fanout_cast(
            context, self.make_msg(method,
                                   router_id=router_id),
            topic=self.topic)

def _notification(self, context, method, routers):
-----------------------------------------------------

引数methodでmetering angetのmethodを呼び出す。引数はrouters。
'l3_agent_scheduler'をプラグインがサポートしている場合は、self._agent_notification(context, method, routers)が処理の実態となる。サポートしていない場合は、以下が呼び出される。::

            self.fanout_cast(context, self.make_msg(method, routers=routers),
                             topic=self.topic)

l3_agent_schedulerがサポートされている場合は、各metering agentに対して、渡されるroutersはそのホストで動作している分だけになるので、効率的なのに対し、l3_agent_schedulerがサポートされていない場合は、routersがすべてのmetering agnetに渡るので、効率的ではない。

def router_deleted(self, context, router_id):
--------------------------------------------------

routerが削除されたことをmetering agentに通知する。::

    def router_deleted(self, context, router_id):
        self._notification_fanout(context, 'router_deleted', router_id)

_notificationではなく、_notification_fanoutである理由は謎。

def routers_updated(self, context, routers):
---------------------------------------------

routerの更新を各metering agentに通知する。::

    def routers_updated(self, context, routers):
        if routers:
            self._notification(context, 'routers_updated', routers)

_notificationで各metering agentに通知する。


def update_metering_label_rules(self, context, routers):
-----------------------------------------------------------

MeteringLabelRuleの更新をmetering agentに通知する。::

    def update_metering_label_rules(self, context, routers):
        self._notification(context, 'update_metering_label_rules', routers)

_notificationを使って、各metering agentに対して関係のあるrouterのみ通知する。


def add_metering_label(self, context, routers):
-----------------------------------------------

MeteringLabelの追加を各metering agentに通知する。::

    def add_metering_label(self, context, routers):
        self._notification(context, 'add_metering_label', routers)

_notificationで通知。


def remove_metering_label(self, context, routers):
-----------------------------------------------------

MeteringLabelの削除を各metering agentに通知する。::

    def remove_metering_label(self, context, routers):
        self._notification(context, 'remove_metering_label', routers)


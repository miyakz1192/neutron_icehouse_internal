======================================================
dhcp-agentの解析
======================================================

class DhcpAgentWithStateReport(DhcpAgent):
---------------------------------------------

dhcp-agentからneutron-serverに対する定期レポートを受け持つクラス。::


    def __init__(self, host=None):
        super(DhcpAgentWithStateReport, self).__init__(host=host)
        self.state_rpc = agent_rpc.PluginReportStateAPI(topics.PLUGIN)
        self.agent_state = {
            'binary': 'neutron-dhcp-agent',
            'host': host,
            'topic': topics.DHCP_AGENT,
            'configurations': {
                'dhcp_driver': cfg.CONF.dhcp_driver,
                'use_namespaces': cfg.CONF.use_namespaces,
                'dhcp_lease_duration': cfg.CONF.dhcp_lease_duration},
            'start_flag': True,
            'agent_type': constants.AGENT_TYPE_DHCP}
        report_interval = cfg.CONF.AGENT.report_interval
        self.use_call = True
        if report_interval:
            self.heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            self.heartbeat.start(interval=report_interval)

self.agent_stateにレポートしたい内容を詰め込んで、FixedIntervalLoopingCallによって定期的にレポート処理が行われるらしい。なお、constantsのdictに例えば、"sample" : "aaa"でも記載してやると、neutron-serverに通達され、neutron agent-showでsample: aaaを見ることができる。
 
なお、PluginReportStateAPIについては別レポートを参照。
FixedIntervalLoopingCallを呼び出し、_report_stateを登録する。以降、greenthreadによって定期実行され、dhcp-agentの状態がneutron-serverに通知される。
FixedIntervalLoopingCallについては別紙参照.greenthreadで_report_stateが定期的に動作する。 


def _report_state(self):
------------------------------

neuron-serverに対する状態のレポート関数::

    def _report_state(self):
        try:
            self.agent_state.get('configurations').update(
                self.cache.get_state())
            ctx = context.get_admin_context_without_session()
            self.state_rpc.report_state(ctx, self.agent_state, self.use_call)
            self.use_call = False
        except AttributeError:
            # This means the server does not support report_state
            LOG.warn(_("Neutron server does not support state report."
                       " State report for this agent will be disabled."))
            self.heartbeat.stop()
            self.run()
            return
        except Exception:
            LOG.exception(_("Failed reporting state!"))
            return
        if self.agent_state.pop('start_flag', None):
            self.run()


agent_stateをキャッシュからupdateしたあと、adminコンテキストでagentのレポートを実行する。なお、最初の一回はself.use_callをTrueに設定し、neutron-serverに対してcallする。その後、Falseに設定されて、castに変化する(なぜ?)。

ここでAttributeErrorが発生したら、neutron-serverへの定期報告をstopする。そしてrunを実行する。その他のエラーの場合は処理を継続するらしい。
(というか、AttributeErrorをcatchするのでいいのか？という気がする)

最後にstart_flagがTrueの場合、runを実行する。なお、agent_stateからstart_flagはpopされるため、定期報告の度にrunが実行されまくるということは無い。

ERROR_CASE: Exceptionが発生した時に、発生原因がわからない可能性がある。ログ出力がちょっと弱い。


def agent_updated(self, context, payload):
----------------------------------------------

agentが更新された際に実行されるメソッド。
needs_resyncがTrueにセットされる。::


    def agent_updated(self, context, payload):
        """Handle the agent_updated notification event."""
        self.needs_resync = True
        LOG.info(_("agent_updated by server side %s!"), payload)

なお、neutron-serverがagent_updatedを呼ぶ契機は、このディレクトリの中の別資料を参照。

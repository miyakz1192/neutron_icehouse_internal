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
FixedIntervalLoopingCallについては別紙参照


==============================
PluginReportStateAPI
==============================

agentのneutron-serverに対する定期的なレポートを受け持つclass::

  class PluginReportStateAPI(proxy.RpcProxy):
      BASE_RPC_API_VERSION = '1.0'
  
      def __init__(self, topic):
          super(PluginReportStateAPI, self).__init__(
              topic=topic, default_version=self.BASE_RPC_API_VERSION)
  
      def report_state(self, context, agent_state, use_call=False):
          msg = self.make_msg('report_state',
                              agent_state={'agent_state':
                                           agent_state},
                              time=timeutils.strtime())
          if use_call:
              return self.call(context, msg, topic=self.topic)
          else:
              return self.cast(context, msg, topic=self.topic)

report_stateでは、agent_stateを指定して、timeutils.strtime()を引数に与えて実行している.dhcp-agentではuse_callを明示的にTrueを設定して一回目のレポートを実行したあと(neutron-serverからの応答を待つ)、Falseを設定しているtimeutilsに関しては別紙を参照。


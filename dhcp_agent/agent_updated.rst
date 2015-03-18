=========================================================
neutron-serverがdhcp-agentのagent_updatedを呼び出す契機
=========================================================

結論
------

結論を最初に書くと、neutron-serverがdhcp-agentのagent_updatedを呼び出す契機は以下の通り。

1) neutron agent-updateコマンドでアップデートした時。

以上。

以下、詳細。


agent_updated
------------------

"neutron/agent/dhcp_agent.py"の以下。::

    def agent_updated(self, context, admin_state_up, host):
        self._cast_message(context, 'agent_updated',
                           {'admin_state_up': admin_state_up}, host)

castを出すらしい。hostを指定する。agentの処理は待たずに復帰する様子。


neutron-serverでの呼び出し契機
--------------------------------------

"neutron/db/agentschedulers_db.py:94"のAgentSchedulerDbMixinクラスのupdate_agentメソッド::

  class AgentSchedulerDbMixin(agents_db.AgentDbMixin):
      """Common class for agent scheduler mixins."""
  
      # agent notifiers to handle agent update operations;
      # should be updated by plugins;
      agent_notifiers = {
          constants.AGENT_TYPE_DHCP: None,
          constants.AGENT_TYPE_L3: None,
          constants.AGENT_TYPE_LOADBALANCER: None,
      }
  
      @staticmethod
      def is_eligible_agent(active, agent):
          if active is None:
              # filtering by activeness is disabled, all agents are eligible
              return True
          else:
              # note(rpodolyaka): original behaviour is saved here: if active
              #                   filter is set, only agents which are 'up'
              #                   (i.e. have a recent heartbeat timestamp)
              #                   are eligible, even if active is False
              return not agents_db.AgentDbMixin.is_agent_down(
                  agent['heartbeat_timestamp'])
  
      def update_agent(self, context, id, agent):
          original_agent = self.get_agent(context, id)
          result = super(AgentSchedulerDbMixin, self).update_agent(
              context, id, agent)
          agent_data = agent['agent']
          agent_notifier = self.agent_notifiers.get(original_agent['agent_type'])
          if (agent_notifier and
              'admin_state_up' in agent_data and
              original_agent['admin_state_up'] != agent_data['admin_state_up']):
              agent_notifier.agent_updated(context,
                                           agent_data['admin_state_up'],
                                           original_agent['host'])
          return result
  
  
update_agentの呼び出し契機
------------------------------
  
"neutron/db/agents_db.py:116:"のAgentDbMixinクラスの以下のメソッド::

    def update_agent(self, context, id, agent):
        agent_data = agent['agent']
        with context.session.begin(subtransactions=True):
            agent = self._get_agent(context, id)
            agent.update(agent_data)
        return self._make_agent_dict(agent)


neutron agent-updateコマンドでアップデートした時。

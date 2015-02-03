============================================
OVSNeutronAgent
============================================


OVSNeutronAgent
================

daemon_loop::

    def daemon_loop(self):
        with polling.get_polling_manager(
            self.minimize_polling,
            self.root_helper,
            self.ovsdb_monitor_respawn_interval) as pm:

            self.rpc_loop(polling_manager=pm)


OVSNeutronAgentの処理の中核。polling.get_polling_managerにより、
polling_managerが有効になる(pm変数として使える)、そのコンテキストのなかで、rpc_loopが呼ばれる。"with polling.get_polling_manager"でrpc_loopがくくられている。rpc_loopが終了すると、pmが自動的に終了するようになっている。

local_vlan_map
================

network(uuid)とlocal vlan idのマッピングを保持。
以下のようなコードにて、作成::

  self.local_vlan_map[net_uuid] = LocalVLANMapping(lvid,
                                                   network_type,
                                                   physical_network,
                                                   segmentation_id)

rpc_loopでネットワーク処理が行われる条件
==========================================

以下のコード::

  if self._agent_has_updates(polling_manager) or ovs_restarted:

_agent_has_updatesがキモになる。::

    def _agent_has_updates(self, polling_manager):
        return (polling_manager.is_polling_required or
                self.updated_ports or
                self.sg_agent.firewall_refresh_needed())

polling_manager.is_polling_requiredがtrueになる条件は？

1) self._is_polling_requiredがTrue、または、
(InterfacePollingMinimizerの場合、ovsdbにinterfaceの更新があった場合にTrueになる)
2) self._force_pollingがTrue、または、
3) self._polling_completedがFalseの場合

self._is_polling_requiredがTrueになる条件(InterfacePollingMinimizer)の場合::

    def _is_polling_required(self):
        # Maximize the chances of update detection having a chance to
        # collect output.
        eventlet.sleep()
        return self._monitor.has_updates

SimpleInterfaceMonitorのhas_updatesがTrueの場合::

    def has_updates(self):
        """Indicate whether the ovsdb Interface table has been updated.

        True will be returned if the monitor process is not active.
        This 'failing open' minimizes the risk of falsely indicating
        the absence of updates at the expense of potential false
        positives.
        """
        return bool(list(self.iter_stdout())) or not self.is_active

"ovsdb-client monitor Interface name ofport"の結果にupdateがある(標準出力のqueueにデータが存在する)、または、is_active(ovsdb-clientコマンドからデータを受け取っている、かつ、killイベントが発火していない)がFalse。

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


rpc_loop
=========

OVS angetの処理の中核。::

    def rpc_loop(self, polling_manager=None):
        if not polling_manager:
            polling_manager = polling.AlwaysPoll()

        sync = True
        ports = set()
        updated_ports_copy = set()
        ancillary_ports = set()
        tunnel_sync = True
        ovs_restarted = False

ここまでで基本的な変数を初期化する。
1. sync = 
2. ports =　現在ovs agentが認識しているportのリスト
3. updated_ports_copy = 
4. ancillary_ports = 現在ovs agentが認識している補助port(br-exのポートなど)のリスト
5. tunnel_sync = True
6. ovs_restarted = False

中核なループは以下::

        while self.run_daemon_loop:
            start = time.time()
            port_stats = {'regular': {'added': 0,
                                      'updated': 0,
                                      'removed': 0},
                          'ancillary': {'added': 0,
                                        'removed': 0}}

ポートの統計情報。regular(br-intのポート)、ancillary(br-ex等)のポート::

            LOG.debug(_("Agent rpc_loop - iteration:%d started"),
                      self.iter_num)
            if sync:
                LOG.info(_("Agent out of sync with plugin!"))
                ports.clear()
                ancillary_ports.clear()
                sync = False
                polling_manager.force_polling()

sync時の処理。portsをクリアし、ancillary_portsをクリアし、polling_managerのforce_pollingを実行する

次の処理では、ovsが再起動された場合の処理::

            ovs_restarted = self.check_ovs_restart()
            if ovs_restarted:
                self.setup_integration_br()
                self.setup_physical_bridges(self.bridge_mappings)
                if self.enable_tunneling:
                    self.setup_tunnel_br()
                    tunnel_sync = True

br-intを初期化して、br-intに接続する外部ブリッジを初期化して(例：br-bond0)、トンネルが有効化の場合はトンネルブリッジを初期化する。

次は、トンネリングが有効化かつ、tunnel_syncがTrueの場合の処理。::

            # Notify the plugin of tunnel IP
            if self.enable_tunneling and tunnel_sync:
                LOG.info(_("Agent tunnel out of sync with plugin!"))
                try:
                    tunnel_sync = self.tunnel_sync()
                except Exception:
                    LOG.exception(_("Error while synchronizing tunnels"))
                    tunnel_sync = True

tunnel_syncを呼び出して、同期処理をおこなう。
次が、portの更新、SGruleの更新、ovsへのportの追加、あるいは、ovsの再起動が発生した場合の処理::

            if self._agent_has_updates(polling_manager) or ovs_restarted:
                try:
                    LOG.debug(_("Agent rpc_loop - iteration:%(iter_num)d - "
                                "starting polling. Elapsed:%(elapsed).3f"),
                              {'iter_num': self.iter_num,
                               'elapsed': time.time() - start})
                    # Save updated ports dict to perform rollback in
                    # case resync would be needed, and then clear
                    # self.updated_ports. As the greenthread should not yield
                    # between these two statements, this will be thread-safe
                    updated_ports_copy = self.updated_ports
                    self.updated_ports = set()
                    reg_ports = (set() if ovs_restarted else ports)
                    port_info = self.scan_ports(reg_ports, updated_ports_copy)
                    LOG.debug(_("Agent rpc_loop - iteration:%(iter_num)d - "
                                "port information retrieved. "
                                "Elapsed:%(elapsed).3f"),
                              {'iter_num': self.iter_num,
                               'elapsed': time.time() - start})
                    # Secure and wire/unwire VIFs and update their status
                    # on Neutron server
                    if (self._port_info_has_changes(port_info) or
                        self.sg_agent.firewall_refresh_needed() or
                        ovs_restarted):
                        LOG.debug(_("Starting to process devices in:%s"),
                                  port_info)
                        # If treat devices fails - must resync with plugin
                        sync = self.process_network_ports(port_info,
                                                          ovs_restarted)
                        LOG.debug(_("Agent rpc_loop - iteration:%(iter_num)d -"
                                    "ports processed. Elapsed:%(elapsed).3f"),
                                  {'iter_num': self.iter_num,
                                   'elapsed': time.time() - start})
                        port_stats['regular']['added'] = (
                            len(port_info.get('added', [])))
                        port_stats['regular']['updated'] = (
                            len(port_info.get('updated', [])))
                        port_stats['regular']['removed'] = (
                            len(port_info.get('removed', [])))
                    ports = port_info['current']
                    # Treat ancillary devices if they exist
                    if self.ancillary_brs:
                        port_info = self.update_ancillary_ports(
                            ancillary_ports)
                        LOG.debug(_("Agent rpc_loop - iteration:%(iter_num)d -"
                                    "ancillary port info retrieved. "
                                    "Elapsed:%(elapsed).3f"),
                                  {'iter_num': self.iter_num,
                                   'elapsed': time.time() - start})

                        if port_info:
                            rc = self.process_ancillary_network_ports(
                                port_info)
                            LOG.debug(_("Agent rpc_loop - iteration:"
                                        "%(iter_num)d - ancillary ports "
                                        "processed. Elapsed:%(elapsed).3f"),
                                      {'iter_num': self.iter_num,
                                       'elapsed': time.time() - start})
                            ancillary_ports = port_info['current']
                            port_stats['ancillary']['added'] = (
                                len(port_info.get('added', [])))
                            port_stats['ancillary']['removed'] = (
                                len(port_info.get('removed', [])))
                            sync = sync | rc

                    polling_manager.polling_completed()
                except Exception:
                    LOG.exception(_("Error while processing VIF ports"))
                    # Put the ports back in self.updated_port
                    self.updated_ports |= updated_ports_copy
                    sync = True

            # sleep till end of polling interval
            elapsed = (time.time() - start)
            LOG.debug(_("Agent rpc_loop - iteration:%(iter_num)d "
                        "completed. Processed ports statistics: "
                        "%(port_stats)s. Elapsed:%(elapsed).3f"),
                      {'iter_num': self.iter_num,
                       'port_stats': port_stats,
                       'elapsed': elapsed})
            if (elapsed < self.polling_interval):
                time.sleep(self.polling_interval - elapsed)
            else:
                LOG.debug(_("Loop iteration exceeded interval "
                            "(%(polling_interval)s vs. %(elapsed)s)!"),
                          {'polling_interval': self.polling_interval,
                           'elapsed': elapsed})
            self.iter_num = self.iter_num + 1

メソッド：scan_ports
=====================

ovs agentに登録されているport(registered_ports)と、更新されたポート(updated_ports)を元に、portをスキャンする。::

    def scan_ports(self, registered_ports, updated_ports=None):
        cur_ports = self.int_br.get_vif_port_set()
        self.int_br_device_count = len(cur_ports)
        port_info = {'current': cur_ports}
        if updated_ports is None:
            updated_ports = set()
        updated_ports.update(self.check_changed_vlans(registered_ports))
        if updated_ports:
            # Some updated ports might have been removed in the
            # meanwhile, and therefore should not be processed.
            # In this case the updated port won't be found among
            # current ports.
            updated_ports &= cur_ports
            if updated_ports:
                port_info['updated'] = updated_ports

        # FIXME(salv-orlando): It's not really necessary to return early
        # if nothing has changed.
        if cur_ports == registered_ports:
            # No added or removed ports to set, just return here
            return port_info

        port_info['added'] = cur_ports - registered_ports
        # Remove all the known ports not found on the integration bridge
        port_info['removed'] = registered_ports - cur_ports
        return port_info

cur_portsにbr-intに接続されているポートを格納。それを"current"のポートとする。registered_portsのポートのうち、VLANIDが変更されたポートをupdated_portsとし、"updated"とする。cur_portsとregistered_portsが等しい場合、port_infoを返す。cur_portsに存在して、registered_portsに存在しないポートが新しく追加されたポートなので、"added"とする。registered_portsに存在して、cur_portsに存在しないポートが削除されたポートなので、"removed"とする。



データ構造：local_vlan_map
===========================

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

ovsが再起動した場合、または、self._agent_has_updatesがTrueになった場合。::

    def _agent_has_updates(self, polling_manager):
        return (polling_manager.is_polling_required or
                self.updated_ports or
                self.sg_agent.firewall_refresh_needed())

1. polling_manager.is_polling_requiredがTrue、または、
2. portに更新があった場合、または、
3. SGruleに更新があった場合 

polling_manager.is_polling_requiredがtrueになる条件は？

1. self._is_polling_required(InterfacePollingMinimizerの場合、ovsdbにinterfaceの更新があった場合にTrueになる)がTrue、または、
2. self._force_pollingがTrue、または、
3. self._polling_completedがFalseの場合

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


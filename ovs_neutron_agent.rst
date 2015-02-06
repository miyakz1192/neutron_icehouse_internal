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

_agent_has_updatesが実行される条件は、"rpc_loopでネットワーク処理が行われる条件"を参照。::

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

port_infoにupdateまたは、added、または、deletedのものがある、または、SGのルールが更新された、または、ovsが再起動した場合は、以下のprocess_network_portsの処理に移行する。::

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


以下、コード::

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

以下、コード::
                except Exception:
                    LOG.exception(_("Error while processing VIF ports"))
                    # Put the ports back in self.updated_port
                    self.updated_ports |= updated_ports_copy
                    sync = True

以下、コード::

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

ovs agentに登録されているport(registered_ports)を元に、更新されたportをスキャンする。復帰値は、現在br-intに接続されているポート、更新されたポート、追加されたポート、削除されたポートが格納されているport_infoという情報(dict)。このメソッドの第１引数は、ovs-agentに登録されている(現在認識している）ポート(IN)。このメソッドの第２引数は更新されたポートが入ってくる(OUT)。::

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


メソッド：check_changed_vlans
===============================

registered_portsのうち、VLANIDが変更があったものを返却する::

    def check_changed_vlans(self, registered_ports):
        """Return ports which have lost their vlan tag.

        The returned value is a set of port ids of the ports concerned by a
        vlan tag loss.
        """
        port_tags = self.int_br.get_port_tag_dict()
        changed_ports = set()
        for lvm in self.local_vlan_map.values():
            for port in registered_ports:
                if (
                    port in lvm.vif_ports
                    and lvm.vif_ports[port].port_name in port_tags
                    and port_tags[lvm.vif_ports[port].port_name] != lvm.vlan
                ):
                    LOG.info(
                        _("Port '%(port_name)s' has lost "
                            "its vlan tag '%(vlan_tag)d'!"),
                        {'port_name': lvm.vif_ports[port].port_name,
                         'vlan_tag': lvm.vlan}
                    )
                    changed_ports.add(port)
        return changed_ports

port_tagsの値はこんな感じ。インタフェース名とVLANIDの対が記録されている。::

  (Pdb) p port_tags
  {u'tap0c8668f9-c9': 1, u'qr-52f5d59d-20': 1}
  (Pdb) 
  (Pdb) self.local_vlan_map.values()
  [<neutron.plugins.openvswitch.agent.ovs_neutron_agent.LocalVLANMapping instance at 0x7fd1993f91b8>]
  (Pdb) 
  (Pdb) p lvm.vif_ports
  {u'52f5d59d-206f-4e42-be1d-e80f2e1d595a': <neutron.agent.linux.ovs_lib.VifPort instance at 0x7fd1993f9128>, u'0c8668f9-c9e8-44b3-bd57-71e0d9fc6778': <neutron.agent.linux.ovs_lib.VifPort instance at 0x7fd1993f92d8>}
  (Pdb) 
  (Pdb) p lvm.vif_ports[port].port_name
  u'qr-52f5d59d-20'
  (Pdb) p lvm.vif_ports[port]
  <neutron.agent.linux.ovs_lib.VifPort instance at 0x7fd1993f9128>
  (Pdb) p lvm.vif_ports[port].port_name
  u'qr-52f5d59d-20'
  (Pdb) 


データ構造：local_vlan_map
===========================

network(uuid)とlocal vlan idのマッピングを保持。
以下のようなコードにて、作成::

  class LocalVLANMapping:
      def __init__(self, vlan, network_type, physical_network, segmentation_id,vif_ports=None):
          if vif_ports is None:
              vif_ports = {}
          self.vlan = vlan
          self.network_type = network_type
          self.physical_network = physical_network
          self.segmentation_id = segmentation_id
          self.vif_ports = vif_ports
          # set of tunnel ports on which packets should be flooded
          self.tun_ofports = set()
  
network uuidのハッシュとして保持。::
                
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

メソッド::process_network_ports
=================================

以下、コード::

    def process_network_ports(self, port_info, ovs_restarted):
        resync_a = False
        resync_b = False
        # TODO(salv-orlando): consider a solution for ensuring notifications
        # are processed exactly in the same order in which they were
        # received. This is tricky because there are two notification
        # sources: the neutron server, and the ovs db monitor process
        # If there is an exception while processing security groups ports
        # will not be wired anyway, and a resync will be triggered
        # TODO(salv-orlando): Optimize avoiding applying filters unnecessarily
        # (eg: when there are no IP address changes)
        self.sg_agent.setup_port_filters(port_info.get('added', set()),
                                         port_info.get('updated', set()))

self.sg_agent.setup_port_filtersで追加した（新規ポート）とVLAN IDが変更したポートについて、SGを設定する。なお、コメントにも記載されているが、SGの設定で例外が発生した場合は、flowの設定が行われずに、途中で処理を終了し、resyncフラグを立てる::

        # VIF wiring needs to be performed always for 'new' devices.
        # For updated ports, re-wiring is not needed in most cases, but needs
        # to be performed anyway when the admin state of a device is changed.
        # A device might be both in the 'added' and 'updated'
        # list at the same time; avoid processing it twice.
        devices_added_updated = (port_info.get('added', set()) |
                                 port_info.get('updated', set()))
        if devices_added_updated:
            start = time.time()
            try:
                skipped_devices = self.treat_devices_added_or_updated(
                    devices_added_updated, ovs_restarted)
                LOG.debug(_("process_network_ports - iteration:%(iter_num)d -"
                            "treat_devices_added_or_updated completed. "
                            "Skipped %(num_skipped)d devices of "
                            "%(num_current)d devices currently available. "
                            "Time elapsed: %(elapsed).3f"),
                          {'iter_num': self.iter_num,
                           'num_skipped': len(skipped_devices),
                           'num_current': len(port_info['current']),
                           'elapsed': time.time() - start})
                # Update the list of current ports storing only those which
                # have been actually processed.
                port_info['current'] = (port_info['current'] -
                                        set(skipped_devices))
            except DeviceListRetrievalError:
                # Need to resync as there was an error with server
                # communication.
                LOG.exception(_("process_network_ports - iteration:%d - "
                                "failure while retrieving port details "
                                "from server"), self.iter_num)
                resync_a = True
        if 'removed' in port_info:
            start = time.time()
            resync_b = self.treat_devices_removed(port_info['removed'])
            LOG.debug(_("process_network_ports - iteration:%(iter_num)d -"
                        "treat_devices_removed completed in %(elapsed).3f"),
                      {'iter_num': self.iter_num,
                       'elapsed': time.time() - start})
        # If one of the above opertaions fails => resync with plugin
        return (resync_a | resync_b)


メソッド::treat_devices_added_or_updated
=========================================

portが追加、または、更新された場合の処理を行う。::

    def treat_devices_added_or_updated(self, devices, ovs_restarted):
        skipped_devices = []
        devices_details_list = []
        for device in devices:
            try:
                # TODO(salv-orlando): Provide bulk API for retrieving
                # details for all devices in one call
                devices_details_list.append(
                    self.plugin_rpc.get_device_details(
                        self.context, device, self.agent_id))
            except Exception as e:
                LOG.debug(_("Unable to get port details for "
                            "%(device)s: %(e)s"),
                          {'device': device, 'e': e})
                raise DeviceListRetrievalError(devices=devices, error=e)

第２引数で指定された個々のportについて、その詳細情報をplugin_rpc.get_device_detailsで得る(APQPでのRPC呼び出し)::

        for details in devices_details_list:
            device = details['device']
            LOG.debug(_("Processing port %s"), device)
            port = self.int_br.get_vif_port_by_id(device)
            if not port:
                # The port disappeared and cannot be processed
                LOG.info(_("Port %s was not found on the integration bridge "
                           "and will therefore not be processed"), device)
                skipped_devices.append(device)
                continue

            if 'port_id' in details:
                LOG.info(_("Port %(device)s updated. Details: %(details)s"),
                         {'device': device, 'details': details})
                self.treat_vif_port(port, details['port_id'],
                                    details['network_id'],
                                    details['network_type'],
                                    details['physical_network'],
                                    details['segmentation_id'],
                                    details['admin_state_up'],
                                    ovs_restarted)
                # update plugin about port status
                # FIXME(salv-orlando): Failures while updating device status
                # must be handled appropriately. Otherwise this might prevent
                # neutron server from sending network-vif-* events to the nova
                # API server, thus possibly preventing instance spawn.
                if details.get('admin_state_up'):
                    LOG.debug(_("Setting status for %s to UP"), device)
                    self.plugin_rpc.update_device_up(
                        self.context, device, self.agent_id, cfg.CONF.host)
                else:
                    LOG.debug(_("Setting status for %s to DOWN"), device)
                    self.plugin_rpc.update_device_down(
                        self.context, device, self.agent_id, cfg.CONF.host)
                LOG.info(_("Configuration for device %s completed."), device)
            else:
                LOG.warn(_("Device %s not defined on plugin"), device)
                if (port and port.ofport != -1):
                    self.port_dead(port)
        return skipped_devices


"for details in devices_details_list:" のところでデバッガーを仕掛けてみる::

  (Pdb) p devices_details_list
  [{u'admin_state_up': True, u'network_id': u'd7f7f51c-1cc1-48a5-b2fb-c85629e29882', u'segmentation_id': None, u'physical_network': None, u'device': u'f8201031-a730-459d-bd18-8a13c778059f', u'port_id': u'f8201031-a730-459d-bd18-8a13c778059f', u'network_type': u'local'}]
  (Pdb) 

device変数には、device_idが入る。device/device_idとportのidは同じ意味らしい。::

  (Pdb) p device
  u'f8201031-a730-459d-bd18-8a13c778059f'
  (Pdb) 
 
ちなみに、このポートはcompute::

  miyakz@icehouse01:~/neutron_icehouse_internal$ neutron port-show f8201031-a730-459d-bd18-8a13c778059f
  +-----------------------+---------------------------------------------------------------------------------+
  | Field                 | Value                                                                           |
  +-----------------------+---------------------------------------------------------------------------------+
  | admin_state_up        | True                                                                            |
  | allowed_address_pairs |                                                                                 |
  | binding:vnic_type     | normal                                                                          |
  | device_id             | f8321c34-1fe8-43c5-9059-2f24377a6ca7                                            |
  | device_owner          | compute:None                                                                    |
  | extra_dhcp_opts       |                                                   
  | fixed_ips             | {"subnet_id": "d530a63f-5887-4e83-9f8e-afd888ceff91", "ip_address": "10.0.0.4"} |
  | id                    | f8201031-a730-459d-bd18-8a13c778059f                                            |
  | mac_address           | fa:16:3e:3f:91:62                                                               |
  | name                  |                                                                                 |
  | network_id            | d7f7f51c-1cc1-48a5-b2fb-c85629e29882                                            |
  | security_groups       | 4bf7a0cb-d7bc-4b64-bc7e-2b30846bd025                                            |
  | status                | BUILD                                                                           |
  | tenant_id             | d66084a3d0d34e6e9f7f52d3ce8ebf7b                                                |
  +-----------------------+---------------------------------------------------------------------------------+
  miyakz@icehouse01:~/neutron_icehouse_internal$ 
   

self.int_br.get_vif_port_by_id(device)の復帰値について調査
portは以下のような感じ::

   (Pdb) p port
   <neutron.agent.linux.ovs_lib.VifPort instance at 0x7ff0492c3878>
   (Pdb) dir(port)
   ['__doc__', '__init__', '__module__', '__str__', 'ofport', 'port_name', 'switch', 'vif_id', 'vif_mac']
   (Pdb) 

 portの各属性は以下のような感じ::

  (Pdb) p port.ofport
  3
  (Pdb) p port.port_name
  u'qvof8201031-a7'
  (Pdb) p port.switch
  <neutron.agent.linux.ovs_lib.OVSBridge object at 0x7ff04a48db50>
  (Pdb) p port.vif_id
  u'f8201031-a730-459d-bd18-8a13c778059f'
  (Pdb) p port.vif_mac
  u'fa:16:3e:3f:91:62'
  (Pdb) 

ofportがovs上の(OpenFlow上の)port番号。ovs自体がOpenFlowベースで作られているからofportというメンバ名なんだろうな。
ちなみに、portがNoneの場合は、skipped_devicesに加えられる。
その後、treat_vif_portでbr-int上にflowを設定する。
設定後、admin_state_upならば、pluginのrpcを呼び出し、neutron-serverのDBをadmin_state_upに変更する。admin_state_upがfalseの場合は、
同様にRPCを呼び出して設定する。
 

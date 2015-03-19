======================================================
dhcp-agentの解析
======================================================

class DhcpAgentWithStateReport(DhcpAgent):
===============================================

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
 
なお、PluginReportStateAPIについては別レポートを参照(plugin_report_state_api.rst) 。
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

なお、neutron-serverがagent_updatedを呼ぶ契機は、このディレクトリの中の別資料を参照(agent_updated.rst)。

class DhcpAgent(manager.Manager):
=======================================

DHCP agnetを表現するクラス。

def _populate_networks_cache(self):
--------------------------------------

Networkのキャッシュ情報を更新する。
NetModelの詳細はdhcp.rstを参照。::


    def _populate_networks_cache(self):
        """Populate the networks cache when the DHCP-agent starts."""
        try:
            existing_networks = self.dhcp_driver_cls.existing_dhcp_networks(
                self.conf,
                self.root_helper
            )
            for net_id in existing_networks:
                net = dhcp.NetModel(self.conf.use_namespaces,
                                    {"id": net_id,
                                     "subnets": [],
                                     "ports": []})
                self.cache.put(net)
        except NotImplementedError:
            # just go ahead with an empty networks cache
            LOG.debug(
                _("The '%s' DHCP-driver does not support retrieving of a "
                  "list of existing networks"),
                self.conf.dhcp_driver
            )


self.dhcp_driver_cls.existing_dhcp_networksを実行し、存在するネットワーク(existing_networksを得る)
なお、dhcp_driver_clsはデフォルトではneutron.agent.linux.dhcp.Dnsmasqである。dnsmasqドライバが認識しているネットワークの一覧を取ってくる。そして、それを列挙して、NetModelクラスを作って、cacheに配置する。

なお、dnsmasqドライバについては、dhcp.rstを参照。

ちなみに、existing_dhcp_networksがdriverに実装されていない場合は、その例外は無視される（単にログがでるだけ）

def call_driver(self, action, network, **action_kwargs):
----------------------------------------------------------------

call_driverは、dhcpドライバ(デフォルトではdnsmasqドライバ)の任意のactionを呼び出す。::

    def call_driver(self, action, network, **action_kwargs):
        """Invoke an action on a DHCP driver instance."""
        LOG.debug(_('Calling driver for network: %(net)s action: %(action)s'),
                  {'net': network.id, 'action': action})
        try:
            # the Driver expects something that is duck typed similar to
            # the base models.
            driver = self.dhcp_driver_cls(self.conf,
                                          network,
                                          self.root_helper,
                                          self.dhcp_version,
                                          self.plugin_rpc)

            getattr(driver, action)(**action_kwargs)
            return True
        except exceptions.Conflict:
            # No need to resync here, the agent will receive the event related
            # to a status update for the network
            LOG.warning(_('Unable to %(action)s dhcp for %(net_id)s: there is '
                          'a conflict with its current state; please check '
                          'that the network and/or its subnet(s) still exist.')
                        % {'net_id': network.id, 'action': action})
        except Exception as e:
            self.needs_resync = True
            if (isinstance(e, common.RemoteError)
                and e.exc_type == 'NetworkNotFound'
                or isinstance(e, exceptions.NetworkNotFound)):
                LOG.warning(_("Network %s has been deleted."), network.id)
            else:
                LOG.exception(_('Unable to %(action)s dhcp for %(net_id)s.')
                              % {'net_id': network.id, 'action': action})

Conflictエラーが発生した場合はそのエラーはログに出力され、無視される。また、それ以外のエラーの場合は、needs_resyncがセットされる。RemoteErrorの場合はNetwork has been deletedというメッセージがでて、それ以外の場合のエラーもログにでるだけで、処理としては続行する。

TODO: dnsmasqドライバがRemoteErrorを送出するか？


def sync_state(self):
--------------------------

dhcp-agentとneutron-serverのネットワークの同期をとって、dnsmasqを起動するメソッド::


    @utils.synchronized('dhcp-agent')
    def sync_state(self):
        """Sync the local DHCP state with Neutron."""
        LOG.info(_('Synchronizing state'))
        pool = eventlet.GreenPool(cfg.CONF.num_sync_threads)
        known_network_ids = set(self.cache.get_network_ids())

        try:
            active_networks = self.plugin_rpc.get_active_networks_info()
            active_network_ids = set(network.id for network in active_networks)
            for deleted_id in known_network_ids - active_network_ids:
                try:
                    self.disable_dhcp_helper(deleted_id)
                except Exception:
                    self.needs_resync = True
                    LOG.exception(_('Unable to sync network state on deleted '
                                    'network %s'), deleted_id)

            for network in active_networks:
                pool.spawn(self.safe_configure_dhcp_for_network, network)
            pool.waitall()
            LOG.info(_('Synchronizing state complete'))

        except Exception:
            self.needs_resync = True
            LOG.exception(_('Unable to sync network state.'))

utils.synchronizedを使っており、これはdhcp-agnetというファイルロックを取る。つまり、同一サーバ内であれば、このメソッドは排他動作するってことになっている。

まず、このメソッドでは、最初にneutron-serverからアクティブなネットワークの一覧を取得する。そして、active_network_idsにそのIDの一覧を入れる。

known_network_ids(dnsmasqドライバが知っているネットワークのID)から、active_network_idsを引いたものが、消去すべきdnsmasqという結果になるので、for deletedのループでself.disable_dhcp_helperを呼び出してdnsmasqを消去する。

そして、active_networksについて、self.safe_configure_dhcp_for_networkを実行する。なお、eventletのスレッドを利用しているため、個々の処理については並行して行われるものと推測される。

[参考]
http://eventlet.net/doc/basic_usage.html

http://eventlet.net/doc/modules/greenpool.html#eventlet.greenpool.GreenPool


ERROR_CASE:これはパフォーマンスの問題が発生する。neutron-serverからすべてのアクティブなネットワークを取ってくる方式は、パフォーマンスに問題が発生する。known_network_idsをフィルター指定するなど、問い合わせに工夫をする必要がある。

def _periodic_resync_helper(self):
-------------------------------------

定期的にループして、needs_resyncが立っている場合はsync_stateを実行する::

    def _periodic_resync_helper(self):
        """Resync the dhcp state at the configured interval."""
        while True:
            eventlet.sleep(self.conf.resync_interval)
            if self.needs_resync:
                self.needs_resync = False
                self.sync_state()


def safe_get_network_info(self, network_id):
----------------------------------------------------

安全にネットワーク情報を取ってくるメソッド。ネットワーク情報の取得に失敗した場合は、needs_resyncを立てる。::

    def safe_get_network_info(self, network_id):
        try:
            network = self.plugin_rpc.get_network_info(network_id)
            if not network:
                LOG.warn(_('Network %s has been deleted.'), network_id)
            return network
        except Exception:
            self.needs_resync = True
            LOG.exception(_('Network %s info call failed.'), network_id)

def enable_dhcp_helper(self, network_id):
---------------------------------------------

self.safe_get_network_infoを実行して、得たnetwork_idを元に、self.configure_dhcp_for_networkを実行する。::

    def enable_dhcp_helper(self, network_id):
        """Enable DHCP for a network that meets enabling criteria."""
        network = self.safe_get_network_info(network_id)
        if network:
            self.configure_dhcp_for_network(network)


def safe_configure_dhcp_for_network(self, network):
------------------------------------------------------------

self.configure_dhcp_for_networkを実行するだけ。::

      def safe_configure_dhcp_for_network(self, network):
          try:
              self.configure_dhcp_for_network(network)
          except (exceptions.NetworkNotFound, RuntimeError):
              LOG.warn(_('Network %s may have been deleted and its resources '
                         'may have already been disposed.'), network.id)
  
def configure_dhcp_for_network(self, network):
------------------------------------------------------------

dhcp driver(デフォルトではdnsmasqドライバ)をのenableメソッドを呼び出す。call_driverのあと、enable_metadataがTrueであれば、metadata proxyを起動する様子。その後、キャッシュを更新する。

なお、dhcpサーバが起動する条件は結構あって、

1. network.admin_state_upがTrue
2. networkにsubnetが設定されている
3. subnetのenable_dhcpがTrue
4. subnetのip_versionが4

となる。コードは以下の通り。::

    def configure_dhcp_for_network(self, network):
        if not network.admin_state_up:
            return

        enable_metadata = self.dhcp_driver_cls.should_enable_metadata(
            self.conf, network)

        for subnet in network.subnets:
            if subnet.enable_dhcp and subnet.ip_version == 4:
                if self.call_driver('enable', network):
                    if self.conf.use_namespaces and enable_metadata:
                        self.enable_isolated_metadata_proxy(network)
                        enable_metadata = False  # Don't trigger twice
                    self.cache.put(network)
                break


def disable_dhcp_helper(self, network_id):
-----------------------------------------------

指定したnetworkのdhcp-serverを無効にするためのヘルパ関数::

    def disable_dhcp_helper(self, network_id):
        """Disable DHCP for a network known to the agent."""
        network = self.cache.get_network_by_id(network_id)
        if network:
            if (self.conf.use_namespaces and
                self.conf.enable_isolated_metadata):
                # NOTE(jschwarz): In the case where a network is deleted, all
                # the subnets and ports are deleted before this function is
                # called, so checking if 'should_enable_metadata' is True
                # for any subnet is false logic here.
                self.disable_isolated_metadata_proxy(network)
            if self.call_driver('disable', network):
                self.cache.remove(network)

まず、キャッシュからnetwork情報を得て、もし、ネットワークの情報が存在する場合、以下の処理を実行。
もし、network namespaceを使うかつ、metadata proxyが有効の場合は、指定されたネットワーク用のmetadata proxyを削除する。
次に、dhcpドライバのdisableを呼び出し、それが成功すれば、キャッシュから、指定されたnetworkの情報を削除する。


def refresh_dhcp_helper(self, network_id):
----------------------------------------------

dhcp-serverの更新の際に呼ばれる関数::

    def refresh_dhcp_helper(self, network_id):
        """Refresh or disable DHCP for a network depending on the current state
        of the network.
        """
        old_network = self.cache.get_network_by_id(network_id)
        if not old_network:
            # DHCP current not running for network.
            return self.enable_dhcp_helper(network_id)

        network = self.safe_get_network_info(network_id)
        if not network:
            return

        old_cidrs = set(s.cidr for s in old_network.subnets if s.enable_dhcp)
        new_cidrs = set(s.cidr for s in network.subnets if s.enable_dhcp)

        if new_cidrs and old_cidrs == new_cidrs:
            self.call_driver('reload_allocations', network)
            self.cache.put(network)
        elif new_cidrs:
            if self.call_driver('restart', network):
                self.cache.put(network)
        else:
            self.disable_dhcp_helper(network.id)

引数で指定されたnetwork(network_id)をキャッシュから取得し、もし、キャッシュに無い場合はdhcp-serverを作成してキャッシュにのせる。neutron-serverから引数で指定されたnetworkの情報を持ってきて、old_cidrsとnew_cidrsを比較。等しければdhcpドライバのreload_allocationsを呼び、違えば、restartを呼ぶ。それ以外は引数で指定されたnetworkのdhcpをdisableする。

ERROR_CASE: 異常系と呼べるかわからないが、引数で指定されたnetworkがサブネットが存在しない状態から、存在する状態に変化した際に、dhcp-serverが作られないのではないかと考える。そのようなケースにこの関数が呼ばれなければ問題ないと思うが。
->あとから気づいたが、create_network_endではrefresh_dhcp_helperは呼び出されないし、networkのサブネットが無い状態から存在する状態への遷移はsubnet_create_endが呼び出される。この時は、refresh_dhcp_helperが呼び出されるが、以下の部分が実行されるだけなので、問題ない。::

        old_network = self.cache.get_network_by_id(network_id)
        if not old_network:
            # DHCP current not running for network.
            return self.enable_dhcp_helper(network_id)

def network_create_end(self, context, payload):
------------------------------------------------------

networkの作成の終わりに呼び出される関数::

    @utils.synchronized('dhcp-agent')
    def network_create_end(self, context, payload):
        """Handle the network.create.end notification event."""
        network_id = payload['network']['id']
        self.enable_dhcp_helper(network_id)

これの呼び出し元は以下。
neutron/api/rpc/agentnotifiers/dhcp_rpc_agent_api.py:62:                    context, 'network_create_end',

_schedule_networkということで、スケジューラの何かのタイミング。networkのスケジューリングについては、scheduler/network/network.rstを参照。
TODO: scheduler/network/network.rstの編集

neutron/api/rpc/agentnotifiers/dhcp_rpc_agent_api.py:107:        cast_required = method != 'network_create_end'
notifyの延長で呼び出される。このnotifyの呼び出し元は以下。
"neutron/api/v2/base.py"の_send_dhcp_notificationの呼び出し元。

1. def update
2. def create(今回はここに該当するものと思われる)
3. def delete

neutron/api/rpc/agentnotifiers/dhcp_rpc_agent_api.py:148:        self._cast_message(context, 'network_create_end',

これは実際にagentのrpcを呼び出す箇所。

ERROR_CASE: サブネットが無いとdhcp-serverを創りださないくせに、network_endが定義されているのはなぜだろう

def network_update_end(self, context, payload):
---------------------------------------------------

ネットワークの更新の際に呼び出される関数::

    @utils.synchronized('dhcp-agent')
    def network_update_end(self, context, payload):
        """Handle the network.update.end notification event."""
        network_id = payload['network']['id']
        if payload['network']['admin_state_up']:
            self.enable_dhcp_helper(network_id)
        else:
            self.disable_dhcp_helper(network_id)


def network_delete_end(self, context, payload):
-------------------------------------------------

ネットワークの削除の際に呼び出される関数::

    @utils.synchronized('dhcp-agent')
    def network_delete_end(self, context, payload):
        """Handle the network.delete.end notification event."""
        self.disable_dhcp_helper(payload['network_id'])

def subnet_update_end(self, context, payload):
---------------------------------------------------

サブネットの更新時に呼び出される関数::

    @utils.synchronized('dhcp-agent')
    def subnet_update_end(self, context, payload):
        """Handle the subnet.update.end notification event."""
        network_id = payload['subnet']['network_id']
        self.refresh_dhcp_helper(network_id)

network_updateだと、admin_state_upがTrueの場合はself.enable_dhcp_helperが呼び出されていたが、subnet_update_endの場合は、self.refresh_dhcp_helperが呼び出される。

なお、subnet_update_endとsubnet_create_endは同じ定義である。

これの呼び出し元は以下。
"neutron/api/v2/base.py"の_send_dhcp_notificationの呼び出し元。

1. def update
2. def create
3. def delete

要するにnetworkと同じ。

def subnet_delete_end(self, context, payload):
-----------------------------------------------------

サブネットの削除時に呼び出される関数::

    @utils.synchronized('dhcp-agent')
    def subnet_delete_end(self, context, payload):
        """Handle the subnet.delete.end notification event."""
        subnet_id = payload['subnet_id']
        network = self.cache.get_network_by_subnet_id(subnet_id)
        if network:
            self.refresh_dhcp_helper(network.id)

def port_update_end(self, context, payload):
--------------------------------------------------

portのupdate時に呼び出される関数::

    @utils.synchronized('dhcp-agent')
    def port_update_end(self, context, payload):
        """Handle the port.update.end notification event."""
        updated_port = dhcp.DictModel(payload['port'])
        network = self.cache.get_network_by_id(updated_port.network_id)
        if network:
            self.cache.put_port(updated_port)
            self.call_driver('reload_allocations', network)

portに関連づくnetwork情報がキャッシュに存在する場合は、キャッシュにupdated_portが代入されたあと、driverのreload_allocationsが呼ばれる。
なお、port_update_endとport_create_endは同じ定義。

ERROR_CASE:networkに関連づくdhcpが何らかの理由により作成が失敗した場合は、port_update_endは何も起こらない。その後、sync_stateで復活すれば良いのだが、どうなるんだろう。configure_dhcp_for_networkでエラーが発生してもneeds_resyncフラグが立たないので、sync_stateは発生しない。

これの呼び出し元は以下。
"neutron/api/v2/base.py"の_send_dhcp_notificationの呼び出し元。

1. def update
2. def create
3. def delete

要するにnetworkと同じ。

def port_delete_end(self, context, payload):
--------------------------------------------------

portが削除された際に呼び出される関数::

    @utils.synchronized('dhcp-agent')
    def port_delete_end(self, context, payload):
        """Handle the port.delete.end notification event."""
        port = self.cache.get_port_by_id(payload['port_id'])
        if port:
            network = self.cache.get_network_by_id(port.network_id)
            self.cache.remove_port(port)
            self.call_driver('reload_allocations', network)

def enable_isolated_metadata_proxy(self, network):
--------------------------------------------------------

dhcp-serverのnetwork namespaceにmetadata proxyを起動する。::

    def enable_isolated_metadata_proxy(self, network):

        # The proxy might work for either a single network
        # or all the networks connected via a router
        # to the one passed as a parameter
        neutron_lookup_param = '--network_id=%s' % network.id
        # When the metadata network is enabled, the proxy might
        # be started for the router attached to the network
        if self.conf.enable_metadata_network:
            router_ports = [port for port in network.ports
                            if (port.device_owner ==
                                constants.DEVICE_OWNER_ROUTER_INTF)]
            if router_ports:
                # Multiple router ports should not be allowed
                if len(router_ports) > 1:
                    LOG.warning(_("%(port_num)d router ports found on the "
                                  "metadata access network. Only the port "
                                  "%(port_id)s, for router %(router_id)s "
                                  "will be considered"),
                                {'port_num': len(router_ports),
                                 'port_id': router_ports[0].id,
                                 'router_id': router_ports[0].device_id})
                neutron_lookup_param = ('--router_id=%s' %
                                        router_ports[0].device_id)

        def callback(pid_file):
            metadata_proxy_socket = cfg.CONF.metadata_proxy_socket
            proxy_cmd = ['neutron-ns-metadata-proxy',
                         '--pid_file=%s' % pid_file,
                         '--metadata_proxy_socket=%s' % metadata_proxy_socket,
                         neutron_lookup_param,
                         '--state_path=%s' % self.conf.state_path,
                         '--metadata_port=%d' % dhcp.METADATA_PORT]
            proxy_cmd.extend(config.get_log_args(
                cfg.CONF, 'neutron-ns-metadata-proxy-%s.log' % network.id))
            return proxy_cmd

        pm = external_process.ProcessManager(
            self.conf,
            network.id,
            self.root_helper,
            network.namespace)
        pm.enable(callback)


metadata proxyを起動する。もし、引数で指定されたnetworkにrouterが接続されていない場合、neutron_lookup_paramに"--network_id"を指定して、metadata proxyを起動する。routerが関連づいている場合は、neutron_lookup_paramに--router_idを指定して、起動する。なお、networkにrouterが複数関連づいている場合は、ログにwarningを吐き出す（謎）。

なお、ProcessManagerの詳細については、processmanager.rstを参照。
TODO: processmanager.rstの編集。

def disable_isolated_metadata_proxy(self, network):
---------------------------------------------------------

metadata proxy の削除を行う関数。::

    def disable_isolated_metadata_proxy(self, network):
        pm = external_process.ProcessManager(
            self.conf,
            network.id,
            self.root_helper,
            network.namespace)
        pm.disable()

class DhcpPluginApi(proxy.RpcProxy):
========================================  

dhcp-agentがneutron-serverのrpcを呼び出す際に使うクラス。
neutron-serverのRPC呼び出しが実装されている。
RPCのバージョンは1.1。
なお、以下のneutron-serverのRPCを呼び出す。 

なお、DhcpPluginApiの初期化は、DhcpAgentの__init__の以下で次のように行われている。::

        ctx = context.get_admin_context_without_session()
        self.plugin_rpc = DhcpPluginApi(topics.PLUGIN,
                                        ctx, self.conf.use_namespaces)

DhcpPluginApiはneutron-serverの以下のRPCを呼び出すメソッドが実装されている。

1. get_active_networks_info
2. get_network_info
3. get_dhcp_port
4. create_dhcp_port
5. update_dhcp_port
6. release_dhcp_port
7. release_port_fixed_ip(dhcp_agent.pyでは未使用)







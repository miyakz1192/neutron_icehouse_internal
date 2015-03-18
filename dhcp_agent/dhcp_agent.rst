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

self.safe_get_network_infoを実行して、得たnetwork_idを元に、self.configure_dhcp_for_networkを実行する。

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

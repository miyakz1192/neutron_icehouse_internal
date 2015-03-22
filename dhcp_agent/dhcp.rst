========================================
dhcp.pyの解析
========================================

このファイルに記載されているオプション
--------------------------------------------

以下の通り::

  OPTS = [
      cfg.StrOpt('dhcp_confs',
                 default='$state_path/dhcp',
                 help=_('Location to store DHCP server config files')),
      cfg.StrOpt('dhcp_domain',
                 default='openstacklocal',
                 help=_('Domain to use for building the hostnames')),
      cfg.StrOpt('dnsmasq_config_file',
                 default='',
                 help=_('Override the default dnsmasq settings with this file')),
      cfg.ListOpt('dnsmasq_dns_servers',
                  help=_('Comma-separated list of the DNS servers which will be '
                         'used as forwarders.'),
                  deprecated_name='dnsmasq_dns_server'),
      cfg.BoolOpt('dhcp_delete_namespaces', default=False,
                  help=_("Delete namespace after removing a dhcp server.")),
      cfg.IntOpt(
          'dnsmasq_lease_max',
          default=(2 ** 24),
          help=_('Limit number of leases to prevent a denial-of-service.')),
  ]
  
dnsmasq_dns_serversがDNS要求のフォワーディング先のDNS serverを指定するオプションである。

class DictModel
===================

Dictを引数にnewすると、そのdictのkeyがメソッド、valueがメソッドの返り値とするようなオブジェクトが出来上がある。

Dictをmethodを持つobjectとして扱いたい場合は便利。なぜ、osloじゃないのかと思うほど便利だと思うのだが。


class DhcpBase(object):
============================

DHCP関連クラスの基本クラス(DeviceManager)がキモっぽい。
こいつが持っているデータは以下。::

        self.conf = conf
        self.network = network
        self.root_helper = root_helper
        self.device_manager = DeviceManager(self.conf,
                                            self.root_helper, plugin)
        self.version = version

class DhcpLocalProcess(DhcpBase):
===================================

Dnsmasqクラスの基盤クラスで基本的なメソッドが定義されている。

def _enable_dhcp(self):
-------------------------

self.networkのサブネットのうち、どれかがenable_dhcpがTrueであればTrueを返す。そうでなければ、Flaseを返す。::

    def _enable_dhcp(self):
        """check if there is a subnet within the network with dhcp enabled."""
        for subnet in self.network.subnets:
            if subnet.enable_dhcp:
                return True
        return False

def enable(self):
--------------------

dhcp-serverの起動を行う。::

    def enable(self):
        """Enables DHCP for this network by spawning a local process."""
        interface_name = self.device_manager.setup(self.network,
                                                   reuse_existing=True)
        if self.active:
            self.restart()
        elif self._enable_dhcp():
            self.interface_name = interface_name
            self.spawn_process()

device_managerをsetupして、activeならrestartを行い、activeでなく、_enable_dhcpがTrueであれば、interface_nameをセットして、spawnする。
activeであれば、restartするというのがクセがあるかんじ。

def disable(self, retain_port=False):
---------------------------------------

enableと対をなすメソッド。dhcp-serverのシャットダウンを行う。::

    def disable(self, retain_port=False):
        """Disable DHCP for this network by killing the local process."""
        pid = self.pid

        if pid:
            if self.active:
                cmd = ['kill', '-9', pid]
                utils.execute(cmd, self.root_helper)
            else:
                LOG.debug(_('DHCP for %(net_id)s is stale, pid %(pid)d '
                            'does not exist, performing cleanup'),
                          {'net_id': self.network.id, 'pid': pid})
            if not retain_port:
                self.device_manager.destroy(self.network,
                                            self.interface_name)
        else:
            LOG.debug(_('No DHCP started for %s'), self.network.id)

        self._remove_config_files()

        if not retain_port:
            if self.conf.dhcp_delete_namespaces and self.network.namespace:
                ns_ip = ip_lib.IPWrapper(self.root_helper,
                                         self.network.namespace)
                try:
                    ns_ip.netns.delete(self.network.namespace)
                except RuntimeError:
                    msg = _('Failed trying to delete namespace: %s')
                    LOG.exception(msg, self.network.namespace)

self.pidがあれば(ファイルにpidが記載されていれば)、かつ、プロセスが起動していれば、kill -KILLを行う(強制停止)。引数：retain_portがTrueであれば、device_managerのdestroyを呼び出して、portを削除する様子。
そのあと、_remove_config_filesを実行して、設定ファイルを削除する。
retain_portがFalseでかつ、self.conf.dhcp_delete_namespacesがTrueかつ、self.network.namespaceがTrueであれば、dhcp-serverのnetwork namespaceを削除する。

def _remove_config_files(self):
----------------------------------

configファイルを消去する::

    def _remove_config_files(self):
        confs_dir = os.path.abspath(os.path.normpath(self.conf.dhcp_confs))
        conf_dir = os.path.join(confs_dir, self.network.id)
        shutil.rmtree(conf_dir, ignore_errors=True)

def get_conf_file_name(self, kind, ensure_conf_dir=False):
------------------------------------------------------------

コンフィグファイル名を返す。::

    def get_conf_file_name(self, kind, ensure_conf_dir=False):
        """Returns the file name for a given kind of config file."""
        confs_dir = os.path.abspath(os.path.normpath(self.conf.dhcp_confs))
        conf_dir = os.path.join(confs_dir, self.network.id)
        if ensure_conf_dir:
            if not os.path.isdir(conf_dir):
                os.makedirs(conf_dir, 0o755)

        return os.path.join(conf_dir, kind)

ensure_conf_dirがTrueの場合はディレクトリを作成する

def _get_value_from_conf_file(self, kind, converter=None):
------------------------------------------------------------

configファイルから設定値を読み込む。::

    def _get_value_from_conf_file(self, kind, converter=None):
        """A helper function to read a value from one of the state files."""
        file_name = self.get_conf_file_name(kind)
        msg = _('Error while reading %s')

        try:
            with open(file_name, 'r') as f:
                try:
                    return converter and converter(f.read()) or f.read()
                except ValueError:
                    msg = _('Unable to convert value in %s')
        except IOError:
            msg = _('Unable to access %s')

        LOG.debug(msg % file_name)
        return None

ファイルを開いてconverterに渡す。converterが指定されていない場合がファイルを開いた内容をそのまま返す。converterにはintなどが指定される。

def pid(self):
-----------------

<confdirpath>/pidのファイルを開いて、その内容をintにして返す。::

    @property
    def pid(self):
        """Last known pid for the DHCP process spawned for this network."""
        return self._get_value_from_conf_file('pid', int)


ちなみに、intにdataを渡すというのは以下のような感じのコードで確認できる。::

  miyakz@icehouse01:/tmp$ cat /tmp/pid 
  1192
  miyakz@icehouse01:/
  >>> f = open("/tmp/pid", "r")
  >>> a = int(f.read())
  >>> a
  1192
  
def active(self):
--------------------

dhcp-serverが生きているかどうかを返す。::

    @property
    def active(self):
        pid = self.pid
        if pid is None:
            return False

        cmdline = '/proc/%s/cmdline' % pid
        try:
            with open(cmdline, "r") as f:
                return self.network.id in f.readline()
        except IOError:
            return False

psコマンドなどを使わずに、procファイルシステムを使っている。psコマンドの結果をパーズするよりも、こっちのほうが手軽で良いかもしれない。ps -e -pidではなく、procファイルを使用しているのがなぜかが気になる。

def interface_name(self):
------------------------------

interfaceの名前を返す。この実装、このクラスでなくて、下位のDnsmasqクラスで実装したらよかったのにな。と思う。::

    @property
    def interface_name(self):
        return self._get_value_from_conf_file('interface')


def interface_name(self, value):
----------------------------------

interface名をvalueで設定する。::

    @interface_name.setter
    def interface_name(self, value):
        interface_file_path = self.get_conf_file_name('interface',
                                                      ensure_conf_dir=True)
        utils.replace_file(interface_file_path, value)


ファイルを新しい値の内容で置き換えているだけ。なお、replace_fileの内容はutils.rstを参照(以下でも記載しておく)。
replace_fileの実装は、新しい値をテンポラリファイルに書き込み、renameしている。unixでは、ファイルシステム上どこからも参照されないinodeがあったとしても、プロセスが使用中であれば、削除されずに残り続ける。interface_name(replace_file)が実行されると、dnsmasqが使っているファイルのinodeが変更されるため、現在起動しているdnsmasqが認識しているinterface名と、ファイルに記載されているinterface名が異なることになり若干の混乱を生む。::

  def replace_file(file_name, data):
      """Replaces the contents of file_name with data in a safe manner.
  
      First write to a temp file and then rename. Since POSIX renames are
      atomic, the file is unlikely to be corrupted by competing writes.
  
      We create the tempfile on the same device to ensure that it can be renamed.
      """
  
      base_dir = os.path.dirname(os.path.abspath(file_name))
      tmp_file = tempfile.NamedTemporaryFile('w+', dir=base_dir, delete=False)
      tmp_file.write(data)
      tmp_file.close()
      os.chmod(tmp_file.name, 0o644)
      os.rename(tmp_file.name, file_name)

以下に、リネーム後のinode番号は、リネーム対象のファイルのinode番号になることを記載しておく::

   miyakz@icehouse01:/tmp$ cat a
   a
   miyakz@icehouse01:/tmp$ cat b
   b
   miyakz@icehouse01:/tmp$ ls -li
   合計 12
   75944 -rw-rw-r-- 1 miyakz miyakz 2  3月 22 13:13 a
   75907 -rw-rw-r-- 1 miyakz miyakz 2  3月 22 13:13 b
   75975 -rw-rw-r-- 1 miyakz miyakz 5  3月 22 12:47 pid
   miyakz@icehouse01:/tmp$ mv a b
   miyakz@icehouse01:/tmp$ ls -li
   合計 8
   75944 -rw-rw-r-- 1 miyakz miyakz 2  3月 22 13:13 b
   75975 -rw-rw-r-- 1 miyakz miyakz 5  3月 22 12:47 pid
   miyakz@icehouse01:/tmp$ 
   miyakz@icehouse01:/tmp$ cat b
   a
   miyakz@icehouse01:/tmp$ 
   
def spawn_process(self):
------------------------------------

中身はない。下位クラスで実装する::

    @abc.abstractmethod
    def spawn_process(self):
        pass

class Dnsmasq(DhcpLocalProcess):
==================================

Dnsmasqドライバの実装。MINIMUM_VERSION = 2.59以上でないと、警告が出る::
    @classmethod
    def check_version(cls):
        ver = 0
        try:
            cmd = ['dnsmasq', '--version']
            out = utils.execute(cmd)
            ver = re.findall("\d+.\d+", out)[0]
            is_valid_version = float(ver) >= cls.MINIMUM_VERSION
            if not is_valid_version:
                LOG.warning(_('FAILED VERSION REQUIREMENT FOR DNSMASQ. '
                              'DHCP AGENT MAY NOT RUN CORRECTLY! '
                              'Please ensure that its version is %s '
                              'or above!'), cls.MINIMUM_VERSION)
        except (OSError, RuntimeError, IndexError, ValueError):
            LOG.warning(_('Unable to determine dnsmasq version. '
                          'Please ensure that its version is %s '
                          'or above!'), cls.MINIMUM_VERSION)
        return float(ver)

versionがfloatになっているところが奇妙に感じる。

def existing_dhcp_networks(cls, conf, root_helper):
---------------------------------------------------------

dhcp-serverが存在しているネットワークを列挙する。
コンフィグファイルが格納されているディレクトリがnetworkのidになっていることを利用したもの。::

    @classmethod
    def existing_dhcp_networks(cls, conf, root_helper):
        """Return a list of existing networks ids that we have configs for."""

        confs_dir = os.path.abspath(os.path.normpath(conf.dhcp_confs))

        return [
            c for c in os.listdir(confs_dir)
            if uuidutils.is_uuid_like(c)
        ]

このメソッドでは、実際にdnsmasqが起動しているかどうかまでは判断していない。

def check_version(cls):
--------------------------

dnsmasqのバージョンチェック。

def spawn_process(self):
----------------------------

dnsmasqを起動するメソッド。大きな流れは以下。

1. dnsmasqの実行コマンドオプションの組み立て
2. --dhcp-range/--dhcp-lease-max/--conf-file/--server/--domainオプションの組み立て
3. network namespaceでdnsmasqの起動

以下、順番に詳細に見てゆく。::

    def spawn_process(self):
        """Spawns a Dnsmasq process for the network."""
        env = {
            self.NEUTRON_NETWORK_ID_KEY: self.network.id,
        }

        cmd = [
            'dnsmasq',
            '--no-hosts',
            '--no-resolv',
            '--strict-order',
            '--bind-interfaces',
            '--interface=%s' % self.interface_name,
            '--except-interface=lo',
            '--pid-file=%s' % self.get_conf_file_name(
                'pid', ensure_conf_dir=True),
            '--dhcp-hostsfile=%s' % self._output_hosts_file(),
            '--addn-hosts=%s' % self._output_addn_hosts_file(),
            '--dhcp-optsfile=%s' % self._output_opts_file(),
            '--leasefile-ro',
        ]

cmdにdnsmasqを起動するためのオプションを記載している。
それぞれの意味は以下の通り。

1.'dnsmasq',
2.'--no-hosts',
3.'--no-resolv',
4.'--strict-order',
5.'--bind-interfaces',
6.'--interface=%s' % self.interface_name,
7.'--except-interface=lo',
8.'--pid-file=%s' % self.get_conf_file_name(
9.'--dhcp-hostsfile=%s' % self._output_hosts_file(),
10.'--addn-hosts=%s' % self._output_addn_hosts_file(),
11.'--dhcp-optsfile=%s' % self._output_opts_file(),
12.'--leasefile-ro',

::




        possible_leases = 0
        for i, subnet in enumerate(self.network.subnets):
            # if a subnet is specified to have dhcp disabled
            if not subnet.enable_dhcp:
                continue
            if subnet.ip_version == 4:
                mode = 'static'
            else:
                # TODO(mark): how do we indicate other options
                # ra-only, slaac, ra-nameservers, and ra-stateless.
                mode = 'static'
            if self.version >= self.MINIMUM_VERSION:
                set_tag = 'set:'
            else:
                set_tag = ''

            cidr = netaddr.IPNetwork(subnet.cidr)

            cmd.append('--dhcp-range=%s%s,%s,%s,%ss' %
                       (set_tag, self._TAG_PREFIX % i,
                        cidr.network,
                        mode,
                        self.conf.dhcp_lease_duration))
            possible_leases += cidr.size

        # Cap the limit because creating lots of subnets can inflate
        # this possible lease cap.
        cmd.append('--dhcp-lease-max=%d' %
                   min(possible_leases, self.conf.dnsmasq_lease_max))

        cmd.append('--conf-file=%s' % self.conf.dnsmasq_config_file)
        if self.conf.dnsmasq_dns_servers:
            cmd.extend(
                '--server=%s' % server
                for server in self.conf.dnsmasq_dns_servers)

        if self.conf.dhcp_domain:
            cmd.append('--domain=%s' % self.conf.dhcp_domain)

        ip_wrapper = ip_lib.IPWrapper(self.root_helper,
                                      self.network.namespace)
        ip_wrapper.netns.execute(cmd, addl_env=env)









class NetModel
==================

Networkを表現するモデルらしい。::

  class NetModel(DictModel):
  
      def __init__(self, use_namespaces, d):
          super(NetModel, self).__init__(d)
  
          self._ns_name = (use_namespaces and
                           "%s%s" % (NS_PREFIX, self.id) or None)
  
      @property
      def namespace(self):
          return self._ns_name
  
class Dnsmasq(DhcpLocalProcess):
=======================================

dhcp-agentのデフォルトのdriver class::

  class Dnsmasq(DhcpLocalProcess):
  (snip)
  
      @classmethod
      def existing_dhcp_networks(cls, conf, root_helper):
          """Return a list of existing networks ids that we have configs for."""
  
          confs_dir = os.path.abspath(os.path.normpath(conf.dhcp_confs))
  
          return [
              c for c in os.listdir(confs_dir)
              if uuidutils.is_uuid_like(c)
          ]
  

existing_dhcp_networksでは、conf.dhcp_confs($state_path/dhcp)をlsして、uuidの名前のついたディレクトリの一覧を文字列で取得する。devstackでは/opt/stack/data/neutron/dhcp/に以下のようなディレクトリが転がっている。::

  miyakz@icehouse01:~/neutron_icehouse_internal$ ls -l /opt/stack/data/neutron/dhcp/
  合計 8
  drwxr-xr-x 2 miyakz miyakz 4096  3月 18 14:39 b202bde4-aab5-431b-89f0-d881a73a3ec9
  drwxr-xr-x 2 miyakz miyakz 4096  3月 18 14:39 d7f7f51c-1cc1-48a5-b2fb-c85629e29882
  miyakz@icehouse01:~/neutron_icehouse_internal$ 
  

========================================
dhcp.rstの解析
========================================

class NetModel
-----------------

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
-------------------------------------

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
  

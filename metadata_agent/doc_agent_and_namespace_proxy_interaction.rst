==========================================
name spaceとmetadata agentの関係
==========================================

関係図
========

以下が参考になる::

  http://d.hatena.ne.jp/pyde/20130914/p1

DHCPあるいは、ルータのnetwork namespaceの中に、neutron-ns-metadata-proxyが起動する。各neutron-ns-metadata-proxyが、neutron-metadata-agentにアクセスする。::

  +--------------------------------------------------------------+
  | +--------------------------+                   network node  |
  | |neutron-ns-metadata-proxy |                                 |
  | |仮想ルータ/DHCP           +---+                             |
  | +--------------------------+   |                             |
  |             .                  |   +-----------------------+ |
  |             .                  +---+ neutron-metadata-agent| |
  | +--------------------------+   |   +-----------------------+ |
  | |neutron-ns-metadata-proxy |   |                             |
  | |仮想ルータ/DHCP           +---+                             |
  | +--------------------------+                                 |
  |             .                                                |
  |             .                                                |
  |                                                              |
  +--------------------------------------------------------------+

neutron-metadata-proxyとneutron-metadata-agentはunix domain soketを使って通信している。neutron-metadata-agentとnovaはHTTP通信をしている。

neutron-ns-metadata-proxy
============================

neutron-ns-metadata-proxyの中身は以下の通り。::

  miyakz@icehouse01:/opt/stack/neutron/neutron.egg-info$ cat `which neutron-ns-metadata-proxy`
  #!/usr/bin/python
  # EASY-INSTALL-ENTRY-SCRIPT: 'neutron==2014.1.4.dev76','console_scripts','neutron-ns-metadata-proxy'
  __requires__ = 'neutron==2014.1.4.dev76'
  import sys
  from pkg_resources import load_entry_point
  
  if __name__ == '__main__':
      sys.exit(
          load_entry_point('neutron==2014.1.4.dev76', 'console_scripts', 'neutron-ns-metadata-proxy')()
      )
  miyakz@icehouse01:/opt/stack/neutron/neutron.egg-info$ 

neutron-ns-metadata-proxyというエントリポイントにアクセスしているだけ。エントリポイントはneutronをインストールしたディレクトリにある。::


  miyakz@icehouse01:/opt/stack/neutron/neutron.egg-info$ pwd
  /opt/stack/neutron/neutron.egg-info
  miyakz@icehouse01:/opt/stack/neutron/neutron.egg-info$ cat entry_points.txt  | grep ns-meta
  neutron-ns-metadata-proxy = neutron.agent.metadata.namespace_proxy:main
  quantum-ns-metadata-proxy = neutron.agent.metadata.namespace_proxy:main
  miyakz@icehouse01:/opt/stack/neutron/neutron.egg-info$ 

neutron.agent.metadata.namespace_proxy:mainにマッピングされる。







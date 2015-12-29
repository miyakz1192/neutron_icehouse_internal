=================================================================
haproxy時のnetwork not foundエラーの解析
=================================================================

実験中になぜか、network not foundになることがあった。
直接の原因について記録を残しておく。

network not foundになったケース::

  DEBUG: keystoneclient.session REQ: curl -g -i -X GET http://192.168.122.84:9696/v2.0/networks.json?fields=id&name=bf285ec8-0e33-4482-b1a9-82a7526c11c2 -H "User-Agent: python-neutronclient" -H "Accept: application/json" -H "X-Auth-Token: {SHA1}9cd4c7dd77609f2c90efdca58f49e2dd8d89fb42"

正常なケース::

  DEBUG: keystoneclient.session REQ: curl -g -i -X GET http://192.168.122.84:9696/v2.0/networks.json?fields=id&id=bf285ec8-0e33-4482-b1a9-82a7526c11c2 -H "User-Agent: python-neutronclient" -H "Accept: application/json" -H "X-Auth-Token: {SHA1}7d7ca5fdb4ec0d00cbd4aae94352d9dc0ae58971"

ある試行では、70並列中、3回はnetwork not foundになった。発生確率は低いと言える。
テストプログラムの中では、port-createにネットワークのIDを指定しているため、
nameフィールドで検索されるのは想定外である。

非haproxy環境では一回も発生していないことから、haproxy環境が原因になったことは
間違いない。ということで解析をすすめる。

環境情報
=========

クライアントバージョン：3.1.0::

  miyakz@lily:~/sources/neutron_tools/load_test$ /usr/bin/neutron --version
  3.1.0
  miyakz@lily:~/sources/neutron_tools/load_test$ 


解析
=====






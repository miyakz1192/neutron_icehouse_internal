=================================================================
haproxy時のUnable to find network with nameエラーの解析
=================================================================

実験中になぜか、Unable to find network with nameになることがあった。
直接の原因について記録を残しておく。

エラーになったケース::

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

Unable to find network with nameが発生した時は、以下のトレースがneutronclientで
発生していた::

  DEBUG: keystoneclient.session REQ: curl -g -i -X GET http://192.168.122.84:9696/v2.0/networks.json?fields=id&name=bf285ec8-0e33-4482-b1a9-82a7526c
  11c2 -H "User-Agent: python-neutronclient" -H "Accept: application/json" -H "X-Auth-Token: {SHA1}f358ecc90054730a0f683018a9a4409f4347b302"
  DEBUG: keystoneclient.session RESP: [200] Date: Tue, 29 Dec 2015 07:27:50 GMT Connection: keep-alive Content-Type: application/json; charset=UTF-8
   Content-Length: 16 X-Openstack-Request-Id: req-bce3958c-600c-449c-a4b0-f97cead64e38 
  RESP BODY: {"networks": []}
  
  ERROR: neutronclient.shell Unable to find network with name 'bf285ec8-0e33-4482-b1a9-82a7526c11c2'
  Traceback (most recent call last):
    File "/usr/lib/python2.7/dist-packages/neutronclient/shell.py", line 814, in run_subcommand
      return run_command(cmd, cmd_parser, sub_argv)
    File "/usr/lib/python2.7/dist-packages/neutronclient/shell.py", line 110, in run_command
      return cmd.run(known_args)
    File "/usr/lib/python2.7/dist-packages/neutronclient/common/command.py", line 29, in run
      return super(OpenStackCommand, self).run(parsed_args)
    File "/usr/lib/python2.7/dist-packages/cliff/display.py", line 92, in run
      column_names, data = self.take_action(parsed_args)
    File "/usr/lib/python2.7/dist-packages/neutronclient/common/command.py", line 35, in take_action
      return self.get_data(parsed_args)
    File "/usr/lib/python2.7/dist-packages/neutronclient/neutron/v2_0/__init__.py", line 493, in get_data
      body = self.args2body(parsed_args)
    File "/usr/lib/python2.7/dist-packages/neutronclient/neutron/v2_0/port.py", line 243, in args2body
      client, 'network', parsed_args.network_id)
    File "/usr/lib/python2.7/dist-packages/neutronclient/neutron/v2_0/__init__.py", line 133, in find_resourceid_by_name_or_id
      parent_id, fields='id')['id']
    File "/usr/lib/python2.7/dist-packages/neutronclient/neutron/v2_0/__init__.py", line 125, in find_resource_by_name_or_id
      fields)
    File "/usr/lib/python2.7/dist-packages/neutronclient/neutron/v2_0/__init__.py", line 111, in _find_resource_by_name
      message=not_found_message, status_code=404)
  NeutronClientException: Unable to find network with name 'bf285ec8-0e33-4482-b1a9-82a7526c11c2'

該当するクライアントのコードを見ると以下::

  116 def find_resource_by_name_or_id(client, resource, name_or_id,                   
  117                                 project_id=None, cmd_resource=None,             
  118                                 parent_id=None, fields=None):                   
  119     try:                                                                        
  120         return find_resource_by_id(client, resource, name_or_id,                
  121                                    cmd_resource, parent_id, fields)             
  122     except exceptions.NeutronClientException:                                   
  123         return _find_resource_by_name(client, resource, name_or_id,             
  124                                       project_id, cmd_resource, parent_id,      
  125                                       fields)  


find_resource_by_idで一度トライして例外が発生した場合に、_find_resource_by_nameを
実行する。_find_resource_by_nameの実行の機会を与えたのは、find_resource_by_idの
エラーなので、直接原因はそれ。なのでそこを攻める。

クライアントのログにはUnable to find network with nameエラーの直前に次の
エラーが出ていた。::

  DEBUG: neutronclient.v2_0.client Error message: <html><body><h1>504 Gateway Time-out</h1>
  The server didn't respond in time.
  </body></html>

haproxyの設定が不足している？原因は、haproxyの以下の設定そうだ。::

  global
  #    daemon
  log 127.0.0.1 local0 debug
  maxconn 50
  nbproc 1

maxconnを1000くらいにあげてみて、再現テストをしてみる。
結果、問題は発生しなかった。

テスト結果詳細
================

詳細は以下。10回試行して問題は発生しなかった。::

  miyakz@lily:~/sources/neutron_tools/load_test$ set -x ; for i in `seq 1 100`; do echo ${i};ruby main.rb >& res ; grep -i unable res; done
  ++ seq 1 100
  + for i in '`seq 1 100`'
  + echo 1
  1
  + ruby main.rb
  + grep --color=auto -i unable res
  + for i in '`seq 1 100`'
  + echo 2
  2
  + ruby main.rb
  + grep --color=auto -i unable res
  + for i in '`seq 1 100`'
  + echo 3
  3
  + ruby main.rb
  + grep --color=auto -i unable res
  + for i in '`seq 1 100`'
  + echo 4
  4
  + ruby main.rb
  + grep --color=auto -i unable res
  + for i in '`seq 1 100`'
  + echo 5
  5
  + ruby main.rb
  + grep --color=auto -i unable res
  + for i in '`seq 1 100`'
  + echo 6
  6
  + ruby main.rb
  + grep --color=auto -i unable res
  + for i in '`seq 1 100`'
  + echo 7
  7
  + ruby main.rb
  + grep --color=auto -i unable res
  + for i in '`seq 1 100`'
  + echo 8
  8
  + ruby main.rb
  + grep --color=auto -i unable res
  + for i in '`seq 1 100`'
  + echo 9
  9
  + ruby main.rb
  + grep --color=auto -i unable res
  + for i in '`seq 1 100`'
  + echo 10
  10
  + ruby main.rb
  + grep --color=auto -i unable res






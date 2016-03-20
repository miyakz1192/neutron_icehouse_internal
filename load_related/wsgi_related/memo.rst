=======================================================
高負荷関連のメモ
=======================================================

どういう流れで、web serverが実行されているのか観点での
調査のメモ::

  (Pdb) 
  > /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(443)handle_one_response()
  -> 'request_line': self.requestline,
  (Pdb) 
  > /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(444)handle_one_response()
  -> 'status_code': status_code[0],
  (Pdb) 
  > /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(445)handle_one_response()
  -> 'body_length': length[0],
  (Pdb) 
  > /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(446)handle_one_response()
  -> 'wall_seconds': finish - start,
  (Pdb) 
  2015-12-12 16:23:39.195 24292 INFO neutron.wsgi [req-5cdc4b35-205a-43aa-b293-287b2b4ecf67 None] 192.168.122.84 - - [12/Dec/2015 16:23:39] "GET /v2.0/networks.json HTTP/1.1" 200 2602 37.887409
  
  --Return--
  > /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(446)handle_one_response()->None
  -> 'wall_seconds': finish - start,
  (Pdb) 
  > /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(286)handle_one_request()
  -> self.server.outstanding_requests -= 1
  (Pdb) 
  --Return--
  > /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(286)handle_one_request()->None
  -> self.server.outstanding_requests -= 1
  (Pdb) 
  > /usr/lib/python2.7/BaseHTTPServer.py(341)handle()
  -> while not self.close_connection:
  (Pdb) 
  > /usr/lib/python2.7/BaseHTTPServer.py(342)handle()
  -> self.handle_one_request()
  (Pdb) 
  
正体は以下。
/usr/lib/python2.7/dist-packages/eventlet/wsgi.py
コードは以下。::

  197 class HttpProtocol(BaseHTTPServer.BaseHTTPRequestHandler):                      
  198     protocol_version = 'HTTP/1.1'                                               
  199     minimum_chunk_size = MINIMUM_CHUNK_SIZE   
  (snip)
  438             if self.server.log_output:                                          
  439                 self.server.log_message(self.server.log_format % {              
  440                     'client_ip': self.get_client_ip(),                          
  441                     'client_port': self.client_address[1],                      
  442                     'date_time': self.log_date_time_string(),                   
  443                     'request_line': self.requestline,                           
  444                     'status_code': status_code[0],                              
  445                     'body_length': length[0],                                   
  446                     'wall_seconds': finish - start,                             
  447                 })  
  (snip)
  667         serv.log.write("(%s) wsgi starting up on %s://%s%s/\n" % ( 
  668             serv.pid, scheme, host, port))   

handle_one_responseメソッドでログが吐き出されている。
あと、eventlet/hub.pyにてtaskletの切り替えが行われている。
多分、eventlet/hub.pyにてtaskletの切り替えが行われ、handle_one_request -> handle_one_responseと
処理が進んでいる。したがって、handle_one_responseで生成したuuidをcreate_portまで伝達できれば、
一貫した印を持ってログを記録できるはずだ。

以下、eventletのwsgiから、そこ上で動作するアプリケーションに渡される情報の経路
を追った。::

  > /usr/lib/python2.7/dist-packages/paste/urlmap.py(205)__call__()
  -> environ['PATH_INFO'] = path_info[len(app_url):]
  (Pdb) *** NameError: name 'ln' is not defined
  (Pdb) l*** NameError: name 'ln' is not defined
  (Pdb) l
  *** NameError: name 'll' is not defined
  (Pdb) l
  200               if domain and domain != host and domain != host+':'+port:
  201                   continue
  202               if (path_info == app_url
  203                   or path_info.startswith(app_url + '/')):
  204                   environ['SCRIPT_NAME'] += app_url
  205  ->                 environ['PATH_INFO'] = path_info[len(app_url):]
  206                   return app(environ, start_response)
  207           environ['paste.urlmap_object'] = self
  208           return self.not_found_application(environ, start_response)
  209   
  210   
  (Pdb) 

create_portのところまでのbtをみることで、wsgiで設定した情報が伝搬できないか
を確認。::

  > /opt/stack/neutron/neutron/plugins/ml2/plugin.py(633)create_port()
  -> LOG.info(_("[DEBUG1] %(uuid)s")%{'uuid': uuid_stamp})
  (Pdb) bt
    /usr/lib/python2.7/dist-packages/eventlet/greenpool.py(80)_spawn_n_impl()
  -> func(*args, **kwargs)
    /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(602)process_request()
  -> proto.__init__(socket, address, self)
    /usr/lib/python2.7/SocketServer.py(649)__init__()
  -> self.handle()
    /usr/lib/python2.7/BaseHTTPServer.py(342)handle()
  -> self.handle_one_request()
    /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(285)handle_one_request()
  -> self.handle_one_response()
    /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(392)handle_one_response()
  -> self.environ['uuid'] = uuid_str
    /usr/lib/python2.7/dist-packages/paste/urlmap.py(206)__call__()
  -> return app(environ, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
  -> resp = self.call_func(req, *args, **self.kwargs)
    /usr/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
  -> return self.func(req, *args, **kwargs)
    /opt/stack/neutron/neutron/openstack/common/middleware/request_id.py(38)__call__()
  -> response = req.get_response(self.application)
    /usr/lib/python2.7/dist-packages/webob/request.py(1320)send()
  -> application, catch_exc_info=False)
    /usr/lib/python2.7/dist-packages/webob/request.py(1284)call_application()
  -> app_iter = application(self.environ, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
  -> resp = self.call_func(req, *args, **self.kwargs)
    /usr/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
  -> return self.func(req, *args, **kwargs)
    /opt/stack/neutron/neutron/openstack/common/middleware/catch_errors.py(38)__call__()
  -> response = req.get_response(self.application)
    /usr/lib/python2.7/dist-packages/webob/request.py(1320)send()
  -> application, catch_exc_info=False)
    /usr/lib/python2.7/dist-packages/webob/request.py(1284)call_application()
  -> app_iter = application(self.environ, start_response)
    /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py(687)__call__()
  -> return self.app(env, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)
    /usr/local/lib/python2.7/dist-packages/routes/middleware.py(136)__call__()
  -> response = self.app(environ, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)
    /usr/local/lib/python2.7/dist-packages/routes/middleware.py(136)__call__()
  -> response = self.app(environ, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)
    /usr/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
  -> resp = self.call_func(req, *args, **self.kwargs)
    /usr/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
  -> return self.func(req, *args, **kwargs)
    /opt/stack/neutron/neutron/api/v2/resource.py(87)resource()
  -> result = method(request=request, **args)
    /opt/stack/neutron/neutron/api/v2/base.py(448)create()
  -> obj = obj_creator(request.context, **kwargs)
  > /opt/stack/neutron/neutron/plugins/ml2/plugin.py(633)create_port()
  -> LOG.info(_("[DEBUG1] %(uuid)s")%{'uuid': uuid_stamp})
  (Pdb) 

environは以下、dec.py(144)同ファイルの130の処理に至るところで変換（抽象化）
されている::

  (Pdb) u
  > /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)
  (Pdb) l
  139                   body = resp
  140                   resp = req.response
  141                   resp.write(body)
  142               if resp is not req.response:
  143                   resp = req.response.merge_cookies(resp)
  144  ->             return resp(environ, start_response)
  145           else:
  146               if self.middleware_wraps:
  147                   args = (self.middleware_wraps,) + args
  148               return self.func(req, *args, **kw)
  149   
  (Pdb) 

environがcreate_portに至る頃には、reqに変換されているようだ::

  > /usr/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
  -> resp = self.call_func(req, *args, **self.kwargs)
  (Pdb) l
  125               req.response = req.ResponseClass()
  126               try:
  127                   args = self.args
  128                   if self.middleware_wraps:
  129                       args = (self.middleware_wraps,) + args
  130  ->                 resp = self.call_func(req, *args, **self.kwargs)
  131               except HTTPException as exc:
  132                   resp = exc
  133               if resp is None:
  134                   ## FIXME: I'm not sure what this should be?
  135                   resp = req.response
  (Pdb) 

キモは同ファイルの以下の行で行われる処理らしい::

  124             req = self.RequestClass(environ)                                                                                                      
"/opt/stack/neutron/neutron/api/v2/base.py(448)create()"
のcreate_portからは以下のように参照できる::

  request.environ

handle_one_responseで生成したUUIDは以下の通り参照できる。::

  (Pdb) p request.environ["uuid"]
  UUID('1d30f7ad-2470-49b2-99e3-06a1801384d9')
  (Pdb) 

wsgi.pyのhandle_one_responseでは以下のようにuuidを入れ込んでいる。::

  387         try:                                                                    
  388             try:                                                                
  389                 uuid_str = uuid.uuid4()                                         
  390 #                import pdb                                                     
  391 #                pdb.set_trace()
  392                 self.environ['uuid'] = uuid_str★ココがポイント
  393                 if self.server.log_output:                                      
  394                     self.server.log_message(DEFAULT_LOG_FORMAT_START % {        
  395                         'client_ip': self.get_client_ip(),                      
  396                         'client_port': self.client_address[1],                  
  397                         'date_time': self.log_date_time_string(),               
  398                         'request_line': self.requestline,                       
  399                         'uuid':         uuid_str                                
  400                     })           

肝心のML2Pluginのcreate_portからはどうやって参照するのか？
結局以下のように、
"/opt/stack/neutron/neutron/api/v2/base.py(448)create()"
で、"request"のcontextのみ渡されているので、肝心の情報をもらうことができない。
ってことで、neutron.context.Contextを拡張してやる。


試しにapi_worker=2,rpc_worker=2で多重実行してみる
===================================================

port-createを多重で実行するテストプログラム::

  net = "bf285ec8-0e33-4482-b1a9-82a7526c11c2"
  count_max=1
  parallel_max=50
  
  for count in 1..count_max do 
    threads = []
    for parallel in 1..parallel_max do
      t = Thread.start(parallel) do |_parallel|
        Thread.pass
        puts "neutron port-create --name port#{_parallel} #{net}"
        `neutron port-create --name port#{_parallel} #{net}`
        sleep 1
        puts "neutron port-delete port#{_parallel}"
        `neutron port-delete port#{_parallel}`
      end
      threads << t
    end 
    threads.each do |t|
      t.join
    end
  end

port-createにかかった時間をログから求めるスクリプト::
  grep neutron.wsgi  /tmp/res | grep -v REQ | grep POST | awk '{print $18}'  | sort -n 

多重度50で実行すると、34secかかったport-createが存在した。
CPU数が1だからか。。。workerが2なので、CPU数を4にしてみる。
もう一度同じスクリプトを実行してみると、11secかかった、port-createが存在した。

1workerあたり1000スレッドということを考えると、性能が悪すぎる。どこで
性能が悪くなっているかを解析する。

と思ったが、50並列だとNSのload averageが10以上と重たくなるので、25並列にした。
この場合だと行って7程度。ちょっと、VM(all in one)の中で、負荷試験ツールを
動作させると、neutron-serverとツールが起動するneutronコマンドの間で、
CPUの喰い合いが発生するため、適切ではない。よって、負荷試験ツールを
別のマシン(neutron-server VMが動作しているVMホスト)で動作させることにする。

別のマシンで動作させることにより、負荷テスト時のneutron-serverの動作VMの
load averageが4未満になった。この時のport-createの最大処理時間は、1.8secであった。
もうちょっと並列度を上げてみて、100で行ってみる。100だとVMホストのload averageが
60を超えるという異常事態になったので、60で行ってみる。
60だとVMホストのload averageが10、neutron-serverのload averageが4ちょっと。
最小処理時間が0.03sec。最大処理時間が1.7secなので、このデータで分析してみる。

最大時間が1.7secとなった回では、以下のように、DEBUG12とDEBUG13の間で約1secかかっている::

  2015-12-14 16:32:26.784 14826 INFO neutron.plugins.ml2.plugin [req-ba052180-0f59-42b6-b100-2ff41caae496 None] [DEBUG12] 6c45ed57-5874-4934-ba2a-357c7e9ebf6d
  2015-12-14 16:32:27.885 14826 INFO neutron.plugins.ml2.plugin [req-ba052180-0f59-42b6-b100-2ff41caae496 None] [DEBUG13] 6c45ed57-5874-4934-ba2a-357c7e9ebf6d


しかし、両区間にはCPU時間を消費する処理はなにもない。::
  

  662             LOG.info(_("[DEBUG12] %(uuid)s")%{'uuid': uuid_stamp})              
  663             self.mechanism_manager.create_port_precommit(mech_context)          
  664                                                                                 
  665         try:                                                                    
  666             self.mechanism_manager.create_port_postcommit(mech_context)         
  667             LOG.info(_("[DEBUG13] %(uuid)s")%{'uuid': uuid_stamp})   

実験中はneutron-serverのload averageは4近くだったことから、単に高負荷であったため
だと考える。

70多重(1回目)
---------------

今度は負荷テストプログラム側の多重度を70にしてみる。なお、CPU数4にメモリは4Gである。

==============    =========
load average
---------------------------
ツール側           NS側
==============    =========
14                4
==============    =========
  
結果。

==============    =========   =========
port-create処理時間
----------------------------------------
最小              最大        平均
==============    =========   =========
0.241192          3.247623    0.8479923714285711
==============    =========   =========

3.2secかかった区間を分析してみる::

  miyakz@icehouse01:~$ grep 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37 /tmp/res
  2015-12-14 16:52:02.017 18919 INFO neutron.wsgi [req-8e6650ee-29cf-425b-a7be-7602e26b5cfc None] WSGI_REQ_START: 192.168.122.1 - - [14/Dec/2015 16:52:02] "POST /v2.0/ports.json HTTP/1.1" 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.232 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG1] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.233 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG2] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.267 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG3] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.295 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG4] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.295 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG5] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.367 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG6] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.370 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG7] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.387 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG8] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.395 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG9] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.396 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG10] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.397 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG11] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.398 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG12] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.573 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG13] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.582 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG14] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:02.624 18919 INFO neutron.plugins.ml2.plugin [req-a4eb0bf4-f886-4213-a211-d8bc0d0b763e None] [DEBUG15] 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  2015-12-14 16:52:05.264 18919 INFO neutron.wsgi [req-6fcd80eb-9cb1-444b-90a3-05f4fb3cab1b None] WSGI_REQ_END 192.168.122.1 - - [14/Dec/2015 16:52:05] "POST /v2.0/ports.json HTTP/1.1" 201 753 3.247623 6d2fca16-ae56-48a5-b3f0-00e5c23d5c37
  miyakz@icehouse01:~$ 

DEBUG15が終わったあと、WSGI_REQ_ENDを出力するまでに時間がかかっている。::

  675         LOG.info(_("[DEBUG15] %(uuid)s")%{'uuid': uuid_stamp})                  
  676         return result 
  
DEBUG15のあとはresultを返すだけなので、問題ない。どこかの経路で
3sec消費しているところがあるはずだ。仮説としては、sleepまたは、
IO処理などで、eventletのタスク切り替えが発生したか。

create_portのところまでのbtを丁寧に追ってみる::

  > /opt/stack/neutron/neutron/plugins/ml2/plugin.py(633)create_port()
  -> LOG.info(_("[DEBUG1] %(uuid)s")%{'uuid': uuid_stamp})
  (Pdb) bt
    /usr/lib/python2.7/dist-packages/eventlet/greenpool.py(80)_spawn_n_impl()
  -> func(*args, **kwargs)
    /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(602)process_request()
  -> proto.__init__(socket, address, self)
    /usr/lib/python2.7/SocketServer.py(649)__init__()
  -> self.handle()
    /usr/lib/python2.7/BaseHTTPServer.py(342)handle()
  -> self.handle_one_request()
    /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(285)handle_one_request()
  -> self.handle_one_response()
    /usr/lib/python2.7/dist-packages/eventlet/wsgi.py(392)handle_one_response()
  -> self.environ['uuid'] = uuid_str

     handle_one_responseで最終的にログを出力するのは以下の箇所
     create_portからここに至るまでに経路を追う。
     455             if self.server.log_output:                                          
     456                 self.server.log_message(self.server.log_format % {              
     457                     'client_ip': self.get_client_ip(),                          
     458                     'client_port': self.client_address[1],                      
     459                     'date_time': self.log_date_time_string(),                   
     460                     'request_line': self.requestline,                           
     461                     'status_code': status_code[0],                              
     462                     'body_length': length[0],                                   
     463                     'wall_seconds': finish - start,                             
     464                     'uuid':         uuid_str                                    
     465                 })      


    /usr/lib/python2.7/dist-packages/paste/urlmap.py(206)__call__()
  -> return app(environ, start_response)

     上位appを呼び出して即座に復帰する。他の処理が入り込む余地は無い。
     206                 return app(environ, start_response)

    /usr/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
  -> resp = self.call_func(req, *args, **self.kwargs)
     
     call_funcでおそらくcreate_portを呼び出して、144でrespを呼び出す。respの正体は謎(TODO: check)
     130                 resp = self.call_func(req, *args, **self.kwargs)                
     131             except HTTPException as exc:                                        
     132                 resp = exc                                                      
     133             if resp is None:                                                    
     134                 ## FIXME: I'm not sure what this should be?                     
     135                 resp = req.response                                             
     136             if isinstance(resp, text_type):                                     
     137                 resp = bytes_(resp, req.charset) ★ここはエンコーディングをしているだけ(時間がかかる要素ではある) 
     138             if isinstance(resp, bytes):                                         
     139                 body = resp                                                     
     140                 resp = req.response                                             
     141                 resp.write(body)                                                
     142             if resp is not req.response:                                        
     143                 resp = req.response.merge_cookies(resp)                         
     144             return resp(environ, start_response)   

    /usr/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
  -> return self.func(req, *args, **kwargs)
     
     funcを呼び出して即復帰
     192     def call_func(self, req, *args, **kwargs):                                  
     193         """Call the wrapped function; override this in a subclass to            
     194         change how the function is called."""                                   
     195         return self.func(req, *args, **kwargs)    

    /opt/stack/neutron/neutron/openstack/common/middleware/request_id.py(38)__call__()
  -> response = req.get_response(self.application)

     create_portを呼び出したあと、そのresponseデータにヘッダを付け加えているだけ。
     32 class RequestIdMiddleware(base.Middleware):                                     
     33                                                                                 
     34     @webob.dec.wsgify                                                           
     35     def __call__(self, req):                                                    
     36         req_id = context.generate_request_id()                                  
     37         req.environ[ENV_REQUEST_ID] = req_id                                    
     38         response = req.get_response(self.application)                           
     39         if HTTP_RESP_HEADER_REQUEST_ID not in response.headers:                 
     40             response.headers.add(HTTP_RESP_HEADER_REQUEST_ID, req_id)           
     41         return response      
    
    /usr/lib/python2.7/dist-packages/webob/request.py(1320)send()
  -> application, catch_exc_info=False)

     create_portを呼び出して、その結果をResponseClassにして返却しているだけ。
     たぶん、request.Responseだと思う(TODO: check)。
     1300     def send(self, application=None, catch_exc_info=False):                     
     1301         """                                                                     
     1302         Like ``.call_application(application)``, except returns a               
     1303         response object with ``.status``, ``.headers``, and ``.body``           
     1304         attributes.                                                             
     1305                                                                                 
     1306         This will use ``self.ResponseClass`` to figure out the class            
     1307         of the response object to return.                                       
     1308                                                                                 
     1309         If ``application`` is not given, this will send the request to          
     1310         ``self.make_default_send_app()``                                        
     1311         """                                                                     
     1312         if application is None:                                                 
     1313             application = self.make_default_send_app()                          
     1314         if catch_exc_info:                                                      
     1315             status, headers, app_iter, exc_info = self.call_application(        
     1316                 application, catch_exc_info=True)                               
     1317             del exc_info                                                        
     1318         else:                                                                   
     1319             status, headers, app_iter = self.call_application(                  
     1320                 application, catch_exc_info=False)                              
     1321         return self.ResponseClass(                                              
     1322             status=status, headerlist=list(headers), app_iter=app_iter) 


    /usr/lib/python2.7/dist-packages/webob/request.py(1284)call_application()
  -> app_iter = application(self.environ, start_response)


     create_portを呼び出して、その結果をoutputに代入して、返しているだけ。
     closeが呼び出される場合がある？？謎(TODO: check)
      1284         app_iter = application(self.environ, start_response)                    
      1285         if output or not captured:                                              
      1286             try:                                                                
      1287                 output.extend(app_iter)                                         
      1288             finally:                                                            
      1289                 if hasattr(app_iter, 'close'):                                  
      1290                     app_iter.close()                                            
      1291             app_iter = output                                                   
      1292         if catch_exc_info:                                                      
      1293             return (captured[0], captured[1], app_iter, captured[2])            
      1294         else:                                                                   
      1295             return (captured[0], captured[1], app_iter)  

    /usr/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
  -> resp = self.call_func(req, *args, **self.kwargs)

     →　上述の通り

    /usr/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
  -> return self.func(req, *args, **kwargs)

     create_portを呼び出して即時復帰するだけ。
     192     def call_func(self, req, *args, **kwargs):                                  
     193         """Call the wrapped function; override this in a subclass to            
     194         change how the function is called."""                                   
     195         return self.func(req, *args, **kwargs)  

    /opt/stack/neutron/neutron/openstack/common/middleware/catch_errors.py(38)__call__()
  -> response = req.get_response(self.application)

     create_port呼び出しをくるむだけ::
     33 class CatchErrorsMiddleware(base.Middleware):                                   
     34                                                                                 
     35     @webob.dec.wsgify                                                           
     36     def __call__(self, req):                                                    
     37         try:                                                                    
     38             response = req.get_response(self.application)                       
     39         except Exception:                                                       
     40             LOG.exception(_LE('An error occurred during '                       
     41                               'processing the request: %s'))                    
     42             response = webob.exc.HTTPInternalServerError()                      
     43         return response  

    /usr/lib/python2.7/dist-packages/webob/request.py(1320)send()
  -> application, catch_exc_info=False)

     →　上述の通り

    /usr/lib/python2.7/dist-packages/webob/request.py(1284)call_application()
  -> app_iter = application(self.environ, start_response)

     →　上述の通り

    /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py(687)__call__()
  -> return self.app(env, start_response)

    create_portを呼び出したあとは即時復帰::
    680         try:                                                                    
    681             self._remove_auth_headers(env)                                      
    682             user_token = self._get_user_token_from_header(env)                  
    683             token_info = self._validate_user_token(user_token, env)             
    684             env['keystone.token_info'] = token_info                             
    685             user_headers = self._build_user_headers(token_info)                 
    686             self._add_headers(env, user_headers)                                
    687             return self.app(env, start_response)     

    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)

  　即座に復帰するのみ
   144             return resp(environ, start_response) 

    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)

    →　上述の通り。

    /usr/local/lib/python2.7/dist-packages/routes/middleware.py(136)__call__()
  -> response = self.app(environ, start_response)

   create_portを呼び出してちょっとしたハッシュの処理をやってから、復帰
   136         response = self.app(environ, start_response) 
   137                                                                                 
   138         # Wrapped in try as in rare cases the attribute will be gone already    
   139         try:                                                                    
   140             del self.mapper.environ                                             
   141         except AttributeError:                                                  
   142             pass                                                                
   143         return response    

    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)

    →　上述の通り。
    
    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)

    →　上述の通り。
    
    /usr/local/lib/python2.7/dist-packages/routes/middleware.py(136)__call__()
  -> response = self.app(environ, start_response)

    →　上述の通り。

    /usr/lib/python2.7/dist-packages/webob/dec.py(144)__call__()
  -> return resp(environ, start_response)
  
    →　上述の通り。

    /usr/lib/python2.7/dist-packages/webob/dec.py(130)__call__()
  -> resp = self.call_func(req, *args, **self.kwargs)

    →　上述の通り。

    /usr/lib/python2.7/dist-packages/webob/dec.py(195)call_func()
  -> return self.func(req, *args, **kwargs)

    →　上述の通り。

    /opt/stack/neutron/neutron/api/v2/resource.py(87)resource()
  -> result = method(request=request, **args)

   resultをシリアライズする処理で時間がかかるかも(TODO: check)
   87             result = method(request=request, **args)★ここでresultを得る
   (snip)
   138         status = action_status.get(action, 200)                                 
   139         body = serializer.serialize(result)   ★　ここで何やらシリアライズをする（時間がかかるかも)
   140         # NOTE(jkoelker) Comply with RFC2616 section 9.7                        
   141         if status == 204:                                                       
   142             content_type = ''                                                   
   143             body = None                                                         
   144                                                                                 
   145         return webob.Response(request=request, status=status,                   
   146                               content_type=content_type,                        
   147                               body=body)   


    /opt/stack/neutron/neutron/api/v2/base.py(448)create()
  -> obj = obj_creator(request.context, **kwargs)

   439         else:                                                                   
   440             obj_creator = getattr(self._plugin, action)                         
   441             if self._collection in body:                                        
   442                 # Emulate atomic bulk behavior                                  
   443                 objs = self._emulate_bulk_create(obj_creator, request,          
   444                                                  body, parent_id)               
   445                 return notify({self._collection: objs})                         
   446             else:                                                               
   447                 kwargs.update({self._resource: body})                           
   448                 request.context.logstamp = request.environ["uuid"]              
   449                 obj = obj_creator(request.context, **kwargs) ★　今回はココ                   
   450                                                                                 
   451                 self._nova_notifier.send_network_change( ★　computeの portの場合はこの処理の延長でeventlet.sleep ①                      
   452                     action, {}, {self._resource: obj})                          
   453                 return notify({self._resource: self._view( ★  computeじゃなくても、この延長で通信するのでsleep ②
   454                     request.context, obj)})    


  > /opt/stack/neutron/neutron/plugins/ml2/plugin.py(633)create_port()
  -> LOG.info(_("[DEBUG1] %(uuid)s")%{'uuid': uuid_stamp})
  (Pdb) 

computeのportの場合はeventlet.sleepが走る　①
DHCP agentにportの追加を通知するところでIOが発生するので、そこで、
eventletの切り替えが走る ②

結論としては、create_portの最後でDHCP agentに通知をするところでIOが走るため②、
ここで、時間を喰うことがある。

[memo]今回、復帰時で遅延が見られたが、create_port呼び出し時で
遅延が発生した場合には、keystoneのvalidationのところで、eventlet
切り替えが発生して遅延したのかもしれない。

70多重(2回目)
----------------

データとしては以下(10sec遅延)。::

  2015-12-15 00:44:19.979 17347 INFO neutron.wsgi [req-4cb9a2d9-9a90-4edd-8018-4bde335601b3 None] WSGI_REQ_START: 192.168.122.1 - - [15/Dec/2015 00:44:19] "POST /v2.0/ports.json HTTP/1.1" cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:20.131 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG1] cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:20.132 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG2] cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:20.236 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG3] cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:20.298 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG4] cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:20.299 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG5] cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:20.411 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG6] cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:20.416 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG7] cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:20.438 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG8] cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:20.454 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG9] cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:20.454 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG10] cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:20.455 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG11] cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:20.455 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG12] cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:20.897 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG13] cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:20.898 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG14] cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:30.008 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG15] cd584e7d-6d00-434e-9e8b-41de8094bc2e
  2015-12-15 00:44:30.770 17347 INFO neutron.wsgi [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] WSGI_REQ_END 192.168.122.1 - - [15/Dec/2015 00:44:30] "POST /v2.0/ports.json HTTP/1.1" 201 753 10.791015 cd584e7d-6d00-434e-9e8b-41de8094bc2e

DEBUG14とDEBUG15の間に通信が発生する。::

  673         LOG.info(_("[DEBUG14] %(uuid)s")%{'uuid': uuid_stamp})                  
  674         self.notify_security_groups_member_updated(context, result)
  675         LOG.info(_("[DEBUG15] %(uuid)s")%{'uuid': uuid_stamp})       

eventlet切り替えが発生するため、妥当といえば、妥当

70多重(3回目)
----------------

データとしては、以下(10sec遅延)::

  2015-12-15 00:44:20.022 17347 INFO neutron.wsgi [req-bb5cc18d-878b-4ead-b913-f3f2aae31272 None] WSGI_REQ_START: 192.168.122.1 - - [15/Dec/2015 00:44:20] "POST /v2.0/ports.json HTTP/1.1" 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:20.911 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG1] 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:20.913 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG2] 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:20.935 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG3] 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:20.967 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG4] 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:20.968 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG5] 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:21.232 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG6] 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:21.300 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG7] 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:21.342 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG8] 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:21.584 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG9] 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:21.585 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG10] 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:21.590 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG11] 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:21.591 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG12] 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:29.998 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG13] 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:29.998 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG14] 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:30.643 17347 INFO neutron.plugins.ml2.plugin [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] [DEBUG15] 279e35e3-f2e6-4a76-8a28-a026f7f56524
  2015-12-15 00:44:30.768 17347 INFO neutron.wsgi [req-cc39df5b-598c-4882-b3e5-a38f00977525 None] WSGI_REQ_END 192.168.122.1 - - [15/Dec/2015 00:44:30] "POST /v2.0/ports.json HTTP/1.1" 201 753 10.746070 279e35e3-f2e6-4a76-8a28-a026f7f56524


DEBUG12とDEBUG13の間には何もない。。。::

  662             LOG.info(_("[DEBUG12] %(uuid)s")%{'uuid': uuid_stamp})              
  663             self.mechanism_manager.create_port_precommit(mech_context)          
  664                                                                                 
  665         try:                                                                    
  666             self.mechanism_manager.create_port_postcommit(mech_context)         
  667             LOG.info(_("[DEBUG13] %(uuid)s")%{'uuid': uuid_stamp})  
    
単にCPUが割当たらなかっただけ？そうすると他の回も単にそうだったんじゃないかと
思ってくる。CPU高負荷かどうかを見分ける方法は？(TODO)

70多重(4回目)
---------------

3回目と同様,DEBUG12とDEBUG13の間で遅延(9sec)発生。

70多重(5回目)
-----------------

データとしては以下(7sec)。まんべんなく遅延している。微妙な路線だ::

  2015-12-15 00:44:46.321 17347 INFO neutron.wsgi [req-7a571011-4848-485c-aba5-b54711ecebca None] WSGI_REQ_START: 192.168.122.1 - - [15/Dec/2015 00:44:46] "POST /v2.0/ports.json HTTP/1.1" 29fa38c0-8901-403b-b796-07fd3be1c734

  最初のところで遅延が発生している(約2sec)。

  2015-12-15 00:44:48.875 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG1] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:48.875 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG2] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:48.896 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG3] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:48.904 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG4] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:48.905 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG5] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:49.057 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG6] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:49.064 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG7] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:49.088 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG8] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:49.097 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG9] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:49.098 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG10] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:49.098 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG11] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:49.099 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG12] 29fa38c0-8901-403b-b796-07fd3be1c734

  ここで少し飛んでいる(約1sec)。この間には何も処理は無いはず・・・

  2015-12-15 00:44:50.971 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG13] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:50.972 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG14] 29fa38c0-8901-403b-b796-07fd3be1c734

  この間に少し飛んでいる(約2sec)。self.notify_security_groups_member_updatedが存在するので遅延は発生する。

  2015-12-15 00:44:52.939 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG15] 29fa38c0-8901-403b-b796-07fd3be1c734

  若干(約0.6sec)飛んでいる。DHCP agentへの通知処理はある。

  2015-12-15 00:44:53.578 17347 INFO neutron.wsgi [req-7bb09cf6-3232-4535-a4dc-396596a312ba None] WSGI_REQ_END 192.168.122.1 - - [15/Dec/2015 00:44:53] "POST /v2.0/ports.json HTTP/1.1" 201 753 7.257756 29fa38c0-8901-403b-b796-07fd3be1c734
  

70多重(6回目)
-----------------

傾向としては1回目と同じ::

  2015-12-15 00:44:46.180 17347 INFO neutron.wsgi [req-f330c73b-95fb-4aba-9105-549374e4f908 None] WSGI_REQ_START: 192.168.122.1 - - [15/Dec/2015 00:44:46] "POST /v2.0/ports.json HTTP/1.1" 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:46.997 17347 INFO neutron.plugins.ml2.plugin [req-d4212807-25e5-4130-97f4-8f8f86fbd0b8 None] [DEBUG1] 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:46.997 17347 INFO neutron.plugins.ml2.plugin [req-d4212807-25e5-4130-97f4-8f8f86fbd0b8 None] [DEBUG2] 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:47.003 17347 INFO neutron.plugins.ml2.plugin [req-d4212807-25e5-4130-97f4-8f8f86fbd0b8 None] [DEBUG3] 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:47.011 17347 INFO neutron.plugins.ml2.plugin [req-d4212807-25e5-4130-97f4-8f8f86fbd0b8 None] [DEBUG4] 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:47.011 17347 INFO neutron.plugins.ml2.plugin [req-d4212807-25e5-4130-97f4-8f8f86fbd0b8 None] [DEBUG5] 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:47.038 17347 INFO neutron.plugins.ml2.plugin [req-d4212807-25e5-4130-97f4-8f8f86fbd0b8 None] [DEBUG6] 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:47.040 17347 INFO neutron.plugins.ml2.plugin [req-d4212807-25e5-4130-97f4-8f8f86fbd0b8 None] [DEBUG7] 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:47.057 17347 INFO neutron.plugins.ml2.plugin [req-d4212807-25e5-4130-97f4-8f8f86fbd0b8 None] [DEBUG8] 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:47.061 17347 INFO neutron.plugins.ml2.plugin [req-d4212807-25e5-4130-97f4-8f8f86fbd0b8 None] [DEBUG9] 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:47.062 17347 INFO neutron.plugins.ml2.plugin [req-d4212807-25e5-4130-97f4-8f8f86fbd0b8 None] [DEBUG10] 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:47.062 17347 INFO neutron.plugins.ml2.plugin [req-d4212807-25e5-4130-97f4-8f8f86fbd0b8 None] [DEBUG11] 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:47.063 17347 INFO neutron.plugins.ml2.plugin [req-d4212807-25e5-4130-97f4-8f8f86fbd0b8 None] [DEBUG12] 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:48.246 17347 INFO neutron.plugins.ml2.plugin [req-d4212807-25e5-4130-97f4-8f8f86fbd0b8 None] [DEBUG13] 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:48.247 17347 INFO neutron.plugins.ml2.plugin [req-d4212807-25e5-4130-97f4-8f8f86fbd0b8 None] [DEBUG14] 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:48.332 17347 INFO neutron.plugins.ml2.plugin [req-6c943d4c-f4c6-4fbf-baa9-747f82be22a6 None] [DEBUG15] 6662df0a-f609-4697-9147-7cff921a285a

   この間で5sec遅延。DHCP agentへのAMQP通信で遅延していると考える。

  2015-12-15 00:44:53.398 17347 INFO neutron.wsgi [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] WSGI_REQ_END 192.168.122.1 - - [15/Dec/2015 00:44:53] "POST /v2.0/ports.json HTTP/1.1" 201 753 7.215790 6662df0a-f609-4697-9147-7cff921a285a

70多重(7回目)
-----------------

5回目と同じ、最初のところで遅延が発生している。::

  2015-12-15 00:44:48.336 17347 INFO neutron.wsgi [req-6c943d4c-f4c6-4fbf-baa9-747f82be22a6 None] WSGI_REQ_START: 192.168.122.1 - - [15/Dec/2015 00:44:48] "POST /v2.0/ports.json HTTP/1.1" cf5d7cbd-9475-4063-a05d-03a44c530c65

  一体ここになにがあるのか(5sec遅延)！？

  2015-12-15 00:44:53.023 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG1] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.023 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG2] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.032 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG3] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.045 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG4] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.046 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG5] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.083 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG6] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.086 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG7] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.100 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG8] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.105 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG9] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.106 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG10] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.106 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG11] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.106 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG12] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.383 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG13] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.384 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG14] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.511 17347 INFO neutron.plugins.ml2.plugin [req-7bb09cf6-3232-4535-a4dc-396596a312ba None] [DEBUG15] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:55.137 17347 INFO neutron.wsgi [req-7bb09cf6-3232-4535-a4dc-396596a312ba None] WSGI_REQ_END 192.168.122.1 - - [15/Dec/2015 00:44:55] "POST /v2.0/ports.json HTTP/1.1" 201 753 6.801107 cf5d7cbd-9475-4063-a05d-03a44c530c65
  
  
70多重(8回目)
-----------------

5回目と同じ::

  2015-12-15 00:44:48.257 17347 INFO neutron.wsgi [req-d4212807-25e5-4130-97f4-8f8f86fbd0b8 None] WSGI_REQ_START: 192.168.122.1 - - [15/Dec/2015 00:44:48] "POST /v2.0/ports.json HTTP/1.1" 751659d0-ed82-4247-84be-60713bf5095c

  ここに一体何が？！

  2015-12-15 00:44:51.012 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG1] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.013 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG2] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.019 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG3] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.031 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG4] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.032 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG5] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.290 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG6] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.301 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG7] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.321 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG8] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.453 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG9] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.454 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG10] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.455 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG11] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.456 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG12] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:52.892 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG13] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:52.893 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG14] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:53.020 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG15] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:54.955 17347 INFO neutron.wsgi [req-7bb09cf6-3232-4535-a4dc-396596a312ba None] WSGI_REQ_END 192.168.122.1 - - [15/Dec/2015 00:44:54] "POST /v2.0/ports.json HTTP/1.1" 201 753 6.697722 751659d0-ed82-4247-84be-60713bf5095c
  

分析
------

遅延が顕著だった70多重(7回目)を分析。
neutron-serverのログを以下のようにgrepする。::

  grep 17347 log | less

遅延が発生した回(cf5d7cbd-9475-4063-a05d-03a44c530c65)を中心に見てみる。::

  2015-12-15 00:44:48.336 17347 INFO neutron.wsgi [req-6c943d4c-f4c6-4fbf-baa9-747f82be22a6 None] WSGI_REQ_START: 192.168.122.1 - - [15/Dec/2015 00:44:48] "POST /v2.0/ports.json HTTP/1.1" cf5d7cbd-9475-4063-a05d-03a44c530c65

  本処理のスタート(cf5d7cbd-9475-4063-a05d-03a44c530c65)のkeystoneアクセスと思われるログが直後に出ている。
  
  2015-12-15 00:44:48.337 17347 DEBUG keystoneclient.middleware.auth_token [-] Authenticating user token __call__ /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py:676
  2015-12-15 00:44:48.337 17347 DEBUG keystoneclient.middleware.auth_token [-] Removing headers from request environment: X-Identity-Status,X-Domain-Id,X-Domain-Name,X-Project-Id,X-Project-Name,X-Project-Domain-Id,X-Project-Domain-Name,X-User-Id,X-User-Name,X-User-Domain-Id,X-User-Domain-Name,X-Roles,X-Service-Catalog,X-User,X-Tenant-Id,X-Tenant-Name,X-Tenant,X-Role _remove_auth_headers /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py:733
  2015-12-15 00:44:48.338 17347 DEBUG keystoneclient.middleware.auth_token [-] Returning cached token _cache_get /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py:1545
  2015-12-15 00:44:48.339 17347 DEBUG keystoneclient.middleware.auth_token [-] Storing token in cache store /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py:1460
  2015-12-15 00:44:48.339 17347 DEBUG keystoneclient.middleware.auth_token [-] Received request from user: 663370576440465fa67ac0f0fd3a8ba6 with project_id : bd5924cd9269430ea2a4c6cace92eda3 and roles: _member_,admin,heat_stack_owner  _build_user_headers /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py:996
  2015-12-15 00:44:48.341 17347 DEBUG routes.middleware [-] No route matched for POST /ports.json __call__ /usr/local/lib/python2.7/dist-packages/routes/middleware.py:101
  2015-12-15 00:44:48.342 17347 DEBUG routes.middleware [-] Matched POST /ports.json __call__ /usr/local/lib/python2.7/dist-packages/routes/middleware.py:105
  2015-12-15 00:44:48.342 17347 DEBUG routes.middleware [-] Route path: '/ports{.format}', defaults: {'action': u'create', 'controller': <wsgify at 140019570919504 wrapping <function resource at 0x7f58d8c78aa0>>} __call__ /usr/local/lib/python2.7/dist-packages/routes/middleware.py:107
  2015-12-15 00:44:48.342 17347 DEBUG routes.middleware [-] Match dict: {'action': u'create', 'controller': <wsgify at 140019570919504 wrapping <function resource at 0x7f58d8c78aa0>>, 'format': u'json'} __call__ /usr/local/lib/python2.7/dist-packages/routes/middleware.py:108
  2015-12-15 00:44:48.343 17347 DEBUG neutron.openstack.common.rpc.amqp [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] Sending port.create.start on notifications.info notify /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:623
  2015-12-15 00:44:48.344 17347 DEBUG neutron.openstack.common.rpc.amqp [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] UNIQUE_ID is 0b8bc546210a41b8b804285ae440863d. _add_unique_id /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:342
  2015-12-15 00:44:48.362 17347 DEBUG neutron.api.v2.base [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] Request body: {u'port': {u'network_id': u'bf285ec8-0e33-4482-b1a9-82a7526c11c2', u'name': u'port40', u'admin_state_up': True}} prepare_request_body /opt/stack/neutron/neutron/api/v2/base.py:591

  その後、cf5d7cbd-9475-4063-a05d-03a44c530c65とは別のport-create処理が開始(処理② )


  2015-12-15 00:44:48.875 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG1] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:48.875 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG2] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:48.896 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG3] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:48.904 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG4] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:48.905 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG5] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:48.923 17347 DEBUG neutron.db.db_base_plugin_v2 [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] Generated mac for network bf285ec8-0e33-4482-b1a9-82a7526c11c2 is fa:16:3e:59:80:df _generate_mac /opt/stack/neutron/neutron/db/db_base_plugin_v2.py:321
  2015-12-15 00:44:48.928 17347 DEBUG neutron.notifiers.nova [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] device_id is not set on port yet. record_port_status_changed /opt/stack/neutron/neutron/notifiers/nova.py:175
  2015-12-15 00:44:49.057 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG6] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:49.064 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG7] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:49.088 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG8] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:49.097 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG9] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:49.098 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG10] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:49.098 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG11] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:49.099 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG12] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:50.951 17347 DEBUG neutron.api.v2.base [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] Request body: {u'port': {u'network_id': u'bf285ec8-0e33-4482-b1a9-82a7526c11c2', u'name': u'port32', u'admin_state_up': True}} prepare_request_body /opt/stack/neutron/neutron/api/v2/base.py:591
  2015-12-15 00:44:50.971 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG13] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:50.972 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG14] 29fa38c0-8901-403b-b796-07fd3be1c734
  2015-12-15 00:44:50.973 17347 DEBUG neutron.openstack.common.rpc.amqp [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] Making asynchronous fanout cast... fanout_cast /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:593
  2015-12-15 00:44:50.973 17347 DEBUG neutron.openstack.common.rpc.amqp [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] UNIQUE_ID is d1410d9812fa4f99ad07f59d95a0d21f. _add_unique_id /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:342

  処理 ②  のDHCP agentへの通信処理開始。ここで、eventlet切り替え。また別のport-create要求の処理が開始する(処理 ③ )。

  2015-12-15 00:44:51.012 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG1] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.013 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG2] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.019 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG3] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.031 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG4] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.032 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG5] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.064 17347 DEBUG neutron.db.db_base_plugin_v2 [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] Generated mac for network bf285ec8-0e33-4482-b1a9-82a7526c11c2 is fa:16:3e:be:a0:8c _generate_mac /opt/stack/neutron/neutron/db/db_base_plugin_v2.py:321
  2015-12-15 00:44:51.071 17347 DEBUG neutron.notifiers.nova [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] device_id is not set on port yet. record_port_status_changed /opt/stack/neutron/neutron/notifiers/nova.py:175
  2015-12-15 00:44:51.290 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG6] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.301 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG7] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.321 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG8] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.453 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG9] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.454 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG10] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.455 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG11] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:51.456 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG12] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:52.892 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG13] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:52.893 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG14] 751659d0-ed82-4247-84be-60713bf5095c
  2015-12-15 00:44:52.895 17347 DEBUG neutron.openstack.common.rpc.amqp [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] Making asynchronous fanout cast... fanout_cast /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:593
  2015-12-15 00:44:52.895 17347 DEBUG neutron.openstack.common.rpc.amqp [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] UNIQUE_ID is 23879ae556784a378c0b78f203942402. _add_unique_id /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:342

  処理 ③  のDHCP agentの通信処理開始。eventlet切り替え。

  2015-12-15 00:44:52.926 17347 DEBUG neutron.scheduler.dhcp_agent_scheduler [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] Network bf285ec8-0e33-4482-b1a9-82a7526c11c2 is hosted already schedule /opt/stack/neutron/neutron/scheduler/dhcp_agent_scheduler.py:72
  2015-12-15 00:44:52.929 17347 DEBUG neutron.api.v2.base [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] Request body: {u'port': {u'network_id': u'bf285ec8-0e33-4482-b1a9-82a7526c11c2', u'name': u'port51', u'admin_state_up': True}} prepare_request_body /opt/stack/neutron/neutron/api/v2/base.py:591
  2015-12-15 00:44:52.939 17347 INFO neutron.plugins.ml2.plugin [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] [DEBUG15] 29fa38c0-8901-403b-b796-07fd3be1c734

  処理 ②  の続きの処理(DEBUG15)から再開

  2015-12-15 00:44:52.940 17347 DEBUG neutron.openstack.common.rpc.amqp [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] Sending port.create.end on notifications.info notify /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:623
  2015-12-15 00:44:52.940 17347 DEBUG neutron.openstack.common.rpc.amqp [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] UNIQUE_ID is 1e07d69ba10044f1b87983b4c7ff36d1. _add_unique_id /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:342
  2015-12-15 00:44:52.981 17347 DEBUG neutron.openstack.common.rpc.amqp [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] Making asynchronous cast on dhcp_agent.icehouse01... cast /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:584
  2015-12-15 00:44:52.981 17347 DEBUG neutron.openstack.common.rpc.amqp [req-9e8bf2e5-ce7c-46d8-85da-da83839faa0e None] UNIQUE_ID is e1f59e79b6744fea92f28a35e5b0ab46. _add_unique_id /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:342
  2015-12-15 00:44:52.994 17347 DEBUG keystoneclient.middleware.auth_token [-] Storing token in cache store /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py:1460
  2015-12-15 00:44:52.994 17347 DEBUG keystoneclient.middleware.auth_token [-] Received request from user: 663370576440465fa67ac0f0fd3a8ba6 with project_id : bd5924cd9269430ea2a4c6cace92eda3 and roles: _member_,admin,heat_stack_owner  _build_user_headers /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py:996
  2015-12-15 00:44:52.995 17347 DEBUG routes.middleware [-] No route matched for GET /networks.json __call__ /usr/local/lib/python2.7/dist-packages/routes/middleware.py:101
  2015-12-15 00:44:52.996 17347 DEBUG routes.middleware [-] Matched GET /networks.json __call__ /usr/local/lib/python2.7/dist-packages/routes/middleware.py:105
  2015-12-15 00:44:52.999 17347 DEBUG routes.middleware [-] Route path: '/networks{.format}', defaults: {'action': u'index', 'controller': <wsgify at 140019570887120 wrapping <function resource at 0x7f58d8ce5ed8>>} __call__ /usr/local/lib/python2.7/dist-packages/routes/middleware.py:107
  2015-12-15 00:44:52.999 17347 DEBUG routes.middleware [-] Match dict: {'action': u'index', 'controller': <wsgify at 140019570887120 wrapping <function resource at 0x7f58d8ce5ed8>>, 'format': u'json'} __call__ /usr/local/lib/python2.7/dist-packages/routes/middleware.py:108
  2015-12-15 00:44:53.020 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG15] 751659d0-ed82-4247-84be-60713bf5095c

  処理 ③  の続きの処理(DEBUG15)から再開

  2015-12-15 00:44:53.021 17347 DEBUG neutron.openstack.common.rpc.amqp [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] Sending port.create.end on notifications.info notify /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:623
  2015-12-15 00:44:53.021 17347 DEBUG neutron.openstack.common.rpc.amqp [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] UNIQUE_ID is 8d0708872a9b4aecb13b2394531f4ebe. _add_unique_id /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:342

  おそらく、処理 ③  のport create update通知の延長で通信が発生するので、本処理が再開


  2015-12-15 00:44:53.023 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG1] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.023 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG2] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.032 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG3] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.045 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG4] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.046 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG5] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.074 17347 DEBUG neutron.db.db_base_plugin_v2 [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] Generated mac for network bf285ec8-0e33-4482-b1a9-82a7526c11c2 is fa:16:3e:b4:00:f4 _generate_mac /opt/stack/neutron/neutron/db/db_base_plugin_v2.py:321
  2015-12-15 00:44:53.078 17347 DEBUG neutron.notifiers.nova [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] device_id is not set on port yet. record_port_status_changed /opt/stack/neutron/neutron/notifiers/nova.py:175
  2015-12-15 00:44:53.083 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG6] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.086 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG7] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.100 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG8] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.105 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG9] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.106 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG10] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.106 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG11] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.106 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG12] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.365 17347 DEBUG neutron.openstack.common.rpc.amqp [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] Making asynchronous cast on dhcp_agent.icehouse01... cast /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:584
  2015-12-15 00:44:53.366 17347 DEBUG neutron.openstack.common.rpc.amqp [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] UNIQUE_ID is fe32bbe26d2f4be7a85a9901d24f10f9. _add_unique_id /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:342
  2015-12-15 00:44:53.378 17347 INFO neutron.wsgi [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] WSGI_REQ_END 192.168.122.1 - - [15/Dec/2015 00:44:53] "GET /v2.0/networks.json?fields=id&id=bf285ec8-0e33-4482-b1a9-82a7526c11c2 HTTP/1.1" 200 275 6.881002 a5b6f7e9-325b-46ed-afcb-2e1aeba88625
  2015-12-15 00:44:53.383 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG13] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.384 17347 INFO neutron.plugins.ml2.plugin [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] [DEBUG14] cf5d7cbd-9475-4063-a05d-03a44c530c65
  2015-12-15 00:44:53.385 17347 DEBUG neutron.openstack.common.rpc.amqp [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] Making asynchronous fanout cast... fanout_cast /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:593
  2015-12-15 00:44:53.385 17347 DEBUG neutron.openstack.common.rpc.amqp [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] UNIQUE_ID is 7b8960a635a1433e8cbc8bfe3f48ebd8. _add_unique_id /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:342
  2015-12-15 00:44:53.390 17347 INFO neutron.wsgi [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] WSGI_REQ_END 192.168.122.1 - - [15/Dec/2015 00:44:53] "DELETE /v2.0/ports/3db27b85-5f36-498a-ac71-35c5ff6acd75.json HTTP/1.1" 204 173 7.081066 20d0cd87-ac39-42ed-a3d7-dd40609d8702
  2015-12-15 00:44:53.398 17347 INFO neutron.wsgi [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] WSGI_REQ_END 192.168.122.1 - - [15/Dec/2015 00:44:53] "POST /v2.0/ports.json HTTP/1.1" 201 753 7.215790 6662df0a-f609-4697-9147-7cff921a285a
  2015-12-15 00:44:53.399 17347 INFO neutron.wsgi [req-bb48c36f-c71b-4ab5-8609-e4f5270b99fb None] WSGI_REQ_START: 192.168.122.1 - - [15/Dec/2015 00:44:53] "POST /v2.0/ports.json HTTP/1.1" 2fd7fe8e-5a38-4f81-a402-9f55c2414c5d
  2015-12-15 00:44:53.400 17347 DEBUG keystoneclient.middleware.auth_token [-] Authenticating user token __call__ /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py:676
  2015-12-15 00:44:53.400 17347 DEBUG keystoneclient.middleware.auth_token [-] Removing headers from request environment: X-Identity-Status,X-Domain-Id,X-Domain-Name,X-Project-Id,X-Project-Name,X-Project-Domain-Id,X-Project-Domain-Name,X-User-Id,X-User-Name,X-User-Domain-Id,X-User-Domain-Name,X-Roles,X-Service-Catalog,X-User,X-Tenant-Id,X-Tenant-Name,X-Tenant,X-Role _remove_auth_headers /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py:733
  2015-12-15 00:44:53.401 17347 DEBUG keystoneclient.middleware.auth_token [-] Returning cached token _cache_get /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py:1545
  2015-12-15 00:44:53.402 17347 DEBUG keystoneclient.middleware.auth_token [-] Storing token in cache store /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py:1460
  2015-12-15 00:44:53.403 17347 DEBUG keystoneclient.middleware.auth_token [-] Received request from user: 663370576440465fa67ac0f0fd3a8ba6 with project_id : bd5924cd9269430ea2a4c6cace92eda3 and roles: _member_,admin,heat_stack_owner  _build_user_headers /usr/local/lib/python2.7/dist-packages/keystoneclient/middleware/auth_token.py:996
  2015-12-15 00:44:53.405 17347 DEBUG routes.middleware [-] No route matched for POST /ports.json __call__ /usr/local/lib/python2.7/dist-packages/routes/middleware.py:101
  2015-12-15 00:44:53.405 17347 DEBUG routes.middleware [-] Matched POST /ports.json __call__ /usr/local/lib/python2.7/dist-packages/routes/middleware.py:105
  2015-12-15 00:44:53.406 17347 DEBUG routes.middleware [-] Route path: '/ports{.format}', defaults: {'action': u'create', 'controller': <wsgify at 140019570919504 wrapping <function resource at 0x7f58d8c78aa0>>} __call__ /usr/local/lib/python2.7/dist-packages/routes/middleware.py:107
  2015-12-15 00:44:53.406 17347 DEBUG routes.middleware [-] Match dict: {'action': u'create', 'controller': <wsgify at 140019570919504 wrapping <function resource at 0x7f58d8c78aa0>>, 'format': u'json'} __call__ /usr/local/lib/python2.7/dist-packages/routes/middleware.py:108
  2015-12-15 00:44:53.407 17347 DEBUG neutron.openstack.common.rpc.amqp [req-7bb09cf6-3232-4535-a4dc-396596a312ba None] Sending port.create.start on notifications.info notify /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:623
  2015-12-15 00:44:53.408 17347 DEBUG neutron.openstack.common.rpc.amqp [req-7bb09cf6-3232-4535-a4dc-396596a312ba None] UNIQUE_ID is 21039b2dba28407799c58f4550a422d6. _add_unique_id /opt/stack/neutron/neutron/openstack/common/rpc/amqp.py:342
  2015-12-15 00:44:53.511 17347 INFO neutron.plugins.ml2.plugin [req-7bb09cf6-3232-4535-a4dc-396596a312ba None] [DEBUG15] cf5d7cbd-9475-4063-a05d-03a44c530c65

  本処理終了。
  解析終わり。

結論：port_createの前段で処理が遅延するのは、keystoneへの通信処理によって、他のtaskletに処理が奪われるから。

対策：不明。eventletを使っている限りは避けられないと言える。multiprocessersなeventletがあればよい？

対策
======

1つのapi_workerに処理が殺到しないようにすればよい。api_workerを増やす


  
参考
=======

今回、wsgi.pyにlogstampの改造を入れている。::

  miyakz@icehouse01:/usr/lib/python2.7/dist-packages/eventlet$ diff -u wsgi.py_org_20151212  wsgi.py
  --- wsgi.py_org_20151212  2015-12-12 17:03:48.050768199 +0900
  +++ wsgi.py 2015-12-14 11:00:20.574518000 +0900
  @@ -5,6 +5,7 @@
   import traceback
   import types
   import warnings
  +import uuid
   
   from eventlet.green import urllib
   from eventlet.green import socket
  @@ -20,9 +21,13 @@
   MAX_TOTAL_HEADER_SIZE = 65536
   MINIMUM_CHUNK_SIZE = 4096
   # %(client_port)s is also available
  -DEFAULT_LOG_FORMAT= ('%(client_ip)s - - [%(date_time)s] "%(request_line)s"'
  -                     ' %(status_code)s %(body_length)s %(wall_seconds).6f')
  -
  +DEFAULT_LOG_FORMAT= ('WSGI_REQ_END %(client_ip)s - - [%(date_time)s] "%(request_line)s"'
  +                     ' %(status_code)s %(body_length)s %(wall_seconds).6f'
  +                     ' %(uuid)s')
  +
  +DEFAULT_LOG_FORMAT_START= ('WSGI_REQ_START: %(client_ip)s - - [%(date_time)s] "%(request_line)s"'
  +                           ' %(uuid)s'
  +                     )
   __all__ = ['server', 'format_date_time']
   
   # Weekday and month names for HTTP date/time formatting; always English!
  @@ -381,6 +386,18 @@
   
           try:
               try:
  +                uuid_str = uuid.uuid4()
  +#                import pdb
  +#                pdb.set_trace()
  +                self.environ['uuid'] = uuid_str
  +                if self.server.log_output:
  +                    self.server.log_message(DEFAULT_LOG_FORMAT_START % {
  +                        'client_ip': self.get_client_ip(),
  +                        'client_port': self.client_address[1],
  +                        'date_time': self.log_date_time_string(),
  +                        'request_line': self.requestline,
  +                        'uuid':         uuid_str
  +                    })
                   result = self.application(self.environ, start_response)
                   if (isinstance(result, _AlreadyHandled)
                       or isinstance(getattr(result, '_obj', None), _AlreadyHandled)):
  @@ -444,6 +461,7 @@
                       'status_code': status_code[0],
                       'body_length': length[0],
                       'wall_seconds': finish - start,
  +                    'uuid':         uuid_str
                   })
   
       def get_client_ip(self):
  miyakz@icehouse01:/usr/lib/python2.7/dist-packages/eventlet$ 

CPythonはGILがあるので、マルチスレッドは性能が出ない。マルチプロセスで対応。::
  http://momijiame.tumblr.com/post/65335100849/%E3%83%9E%E3%83%AB%E3%83%81%E3%83%97%E3%83%AD%E3%82%BB%E3%82%B9%E3%81%A7-eventlet-%E3%81%AE-wsgi-%E3%82%B5%E3%83%BC%E3%83%90%E3%82%92%E5%8B%95%E3%81%8B%E3%81%99











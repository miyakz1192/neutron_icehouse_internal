=====================================================
HA関連
=====================================================

NeutronServerの冗長化や、NetworkNodeの冗長化はそれなりに行われているが、
neutron*agent単体の信頼性向上はまだ行われていない。

結局は、processを監視してdownしていれば、そのprocessをkillしたあと、
起動すれば良いだけである。その素材として有力なのが、monitである。

http://techblog.clara.jp/2014/09/centos7_vol5_openvz_docker-install/









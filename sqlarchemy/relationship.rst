=============================================
sqlarchemyでのテーブル間の関係定義関連の情報
=============================================

まとめ　
=========

CASCADEについては以下がわかりやすい
http://www.dbonline.jp/mysql/table/index12.html

sqlarchemyを使ったテーブルのリレーションシップ４例(1:1,N:1,1:M,N:M)。わかりやすい
http://momijiame.tumblr.com/post/27327972441/python-o-r-sqlalchemy-4

sqlarchemyのリファレンスマニュアル(backrefの説明)
http://docs.sqlalchemy.org/en/rel_1_0/orm/backref.html

primaryjoinの例(Filmとlanguageの関係、たとえがわかりやすい)
http://blog.hirokiky.org/2013/04/06/multiple_relationship_to_one_table_by_sqlalchemy.html

relationship関数のlazyに関する記述
http://docs.sqlalchemy.org/en/latest/orm/loading_relationships.html
lazy=joinedだとJOINを発行した際にデータを読み込んでくる指定になる。

疑問点１
==========

relationship関数のforeign_keysについて。
まず、MeteringLabelRuleのテーブル定義::

  class MeteringLabelRule(model_base.BASEV2, models_v2.HasId):
      direction = sa.Column(sa.Enum('ingress', 'egress',
                                    name='meteringlabels_direction'))
      remote_ip_prefix = sa.Column(sa.String(64))
      metering_label_id = sa.Column(sa.String(36),
                                    sa.ForeignKey("meteringlabels.id",
                                                  ondelete="CASCADE"),
                                    nullable=False)
      excluded = sa.Column(sa.Boolean, default=False)

MeteringLabelのDBテーブル定義。::

  class MeteringLabel(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
      name = sa.Column(sa.String(255))
      description = sa.Column(sa.String(1024))
      rules = orm.relationship(MeteringLabelRule, backref="label",
                               cascade="delete", lazy="joined")
      routers = orm.relationship(
          l3_db.Router,
          primaryjoin="MeteringLabel.tenant_id==Router.tenant_id",
          foreign_keys='MeteringLabel.tenant_id',
          uselist=True)

routerの定義で、orm.relationship関数にforeign_keysを指定しているけど、これは、どのテーブルにとっての外部キーなんだろう。




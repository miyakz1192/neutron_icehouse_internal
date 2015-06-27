================================================
metering dbの解析
================================================

モデル図
===========

モデル図は以下の通り。::


 +----------------+ N         M  +--------+
 | MeteringLabel  +--------------+ Router | 
 +------+---------+              +--------+
        | 1
        |
        | N
 +------+-----------+
 | MeteringLabelRule|
 +------------------+


class MeteringLabelRule(model_base.BASEV2, models_v2.HasId):
=============================================================

DBのテーブル、MeteringLabelRule。::


  class MeteringLabelRule(model_base.BASEV2, models_v2.HasId):
      direction = sa.Column(sa.Enum('ingress', 'egress',
                                    name='meteringlabels_direction'))
      remote_ip_prefix = sa.Column(sa.String(64))
      metering_label_id = sa.Column(sa.String(36),
                                    sa.ForeignKey("meteringlabels.id",
                                                  ondelete="CASCADE"),
                                    nullable=False)
      excluded = sa.Column(sa.Boolean, default=False)


directionはingressとegressのみが指定可能。
外部キー：metering_label_id

metering_labelが消去された時、MeteringLabelRuleも同時に削除される。


class MeteringLabel(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
======================================================================

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

MeteringLabelRuleとの関連を持っており、JOINが発行された際に、MeteringLabelRuleを積極的に読み込んでくる。また、MeteringLabelが消去された際には、同時に、関連するMeteringLabelRuleも削除する。


class MeteringDbMixin(metering.MeteringPluginBase,base_db.CommonDbMixin):
=====================================================================

neutron-server側でmixinするDB操作用のクラス。


def __init__(self):
------------------------

dbapi.register_modelsですべてのテーブルを作成する。
MeteringAgentNotifyAPIを初期化してmeter_rpc変数に格納する。ただし、この変数は使われない。


def _make_metering_label_dict(self, metering_label, fields=None):
-------------------------------------------------------------------

labelの情報をdict形式にする。

def create_metering_label(self, context, metering_label):
-------------------------------------------------------------

MeteringLabelのレコードを作成する。

1. APIリクエストから_get_tenant_id_for_createでtenant_idを得る
2. トランザクションを開いてMeteringLabelを作成
3. dictにして返す。
 
バリデーションは行っていない。


def delete_metering_label(self, context, label_id):
-------------------------------------------------------

_get_by_idでlabel_idをキーにレコードを検索し、存在すれば削除。存在しなければ404を返す。

def get_metering_label(self, context, label_id, fields=None):
-----------------------------------------------------------------

MeteringLabelを返す。結果はdict。なければ404。


def get_metering_labels(self, context, filters=None, fields=None,
-------------------------------------------------------------------

MeteringLabelのリストを返す。


def _make_metering_label_rule_dict(self, metering_label_rule, fields=None):
--------------------------------------------------------------------

MeteringLabelRuleのdictを作って返す。


def get_metering_label_rules(self, context, filters=None, fields=None,
---------------------------------------------------------------------

MeteringLabelRuleのリストをdictにして返す。

def get_metering_label_rule(self, context, rule_id, fields=None):
------------------------------------------------------------------

MeteringLabelRuleのget。dictにして返す。


def _validate_cidr(self, context, label_id, remote_ip_prefix,direction, excluded):
----------------------------------------------------------------

MeteringLabelに新規に追加するルールのcidrが既存のルールのcidrとオーバラップしている場合はエラーにする。cidrのオーバラップの検出範囲は、新規に追加するルールのdirectionとexcludedが同じ範囲。言い換えれば、directionまたはexcludedが違えば、ルール間でcidrが重なっていても良い。


def create_metering_label_rule(self, context, metering_label_rule):
-------------------------------------------------------------------

MeteringLabelRuleを作成する。チェックは、_validate_cidrを実行。それ以外のバリデーションは無い。

def delete_metering_label_rule(self, context, rule_id):
--------------------------------------------------------

MeteringLabelRuleを削除する。(似たようなメソッドが繰り返し定義されているなぁ)


def _get_metering_rules_dict(self, metering_label):
-------------------------------------------------------

MeteringLabelに関連づくMeteringLabelRuleの情報をdictにして返す。


def _make_router_dict(self, router):
-----------------------------------------

routersの情報をdictにして返す。


def _process_sync_metering_data(self, labels):
--------------------------------------------------

システムに存在するすべてのMeteringLabelに関連づく、すべてのルータの情報を列挙したdictを作る。個々のルータの情報には、ルータに関連づくMeteringLabelのIDとMeteringLabelRuleが含まれる。



def get_sync_data_metering(self, context, label_id=None, router_ids=None):
-------------------------------------------------------------------

データの取得メソッド。
label_idが指定されている場合は、それをキーとして、MeteringLabelを検索してlabels変数に格納。
label_idが指定されていなく、かつ、router_idsが指定されている場合は、router_idsで指定されたrouterの一覧と、MeteringLabelを結合したテーブルを作って、labels変数に格納。
両方とも指定されていない場合は、すべてのlabelをlabels変数に格納。

_process_sync_metering_dataにlabels変数を入れて、return










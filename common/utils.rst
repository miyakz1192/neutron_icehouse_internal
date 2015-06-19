=============================================
class cache_method_results(object):
=============================================

このクラスは、オブジェクトメソッドのみに使われることを
前提としたデコレータである。

インスタンス変数
-----------------

1. func: デコレータ対象の関数を格納
2. _first_call: なぞ。Trueに設定されている。
3. _not_cached: 関数の呼び出しがキャッシュされていない場合の印(object型)

_not_cachedが定数ではなく、instance変数なのかは理由は謎すぎる。

def __init__(self, func):
---------------------------

各変数の初期化を行い、functools.update_wrapperを使っている。このfunctool自体はなぞ。


def _get_from_cache(self, target_self, *args, **kwargs):
-----------------------------------------------------------

修飾された(?)関数名を組み立て、func_nameローカル変数に代入しておく。
func_nameとargsとkwargsをタプルとして結合して、キャッシュ(dict)を検索する。検索にヒットしない場合は、self._not_cachedを返す。

検索結果が、self._not_cachedの場合は、funcを実際に呼び出し、
キャッシュに登録する。

func_nameと引数(args)と追加の引数(kwargs)をキーとして、値がfuncの返り値となるようなdictを形成する。

def __call__(self, target_self, *args, **kwargs):
---------------------------------------------------

target_selfが"_cache"というメソッドを持っていない場合、例外を上げる。

次に、target_selfの_cacheがnulの場合かつ、self._first_callがTrueの場合には、デバッグメッセージを出して、self._first_callをFalseに設定する。self._first_callがFalseの場合は、self.funcを呼び出して、その復帰値をreturn

target_selfの_cacheがnul出ない場合は、self._get_from_cacheを呼び出し、その復帰値をreturn


def __get__(self, obj, objtype):
---------------------------------

functools.partial(なぞ)を呼び出して、その復帰値をreturn。つまり、以下の１行を実行。::

        return functools.partial(self.__call__, obj)


def read_cached_file(filename, cache_info, reload_func=None):
===================================================================

以下とのこと::

    """Read from a file if it has been modified.

    :param cache_info: dictionary to hold opaque cache.
    :param reload_func: optional function to be called with data when
                        file is reloaded due to a modification.

    :returns: data from file


cache_infoが無い、または、キャッシュファイルの最終更新時刻と、cache_infoの最終更新時刻が異なる場合は、キャッシュファイルからデータを読み込み、cache_infoの最終更新時刻をキャッシュファイルのそれに変更する。さらに、reload_funcが設定されている場合はそれを呼び出す。









from django.urls import path
from bom import views

app_name = 'bom'
urlpatterns = [
    # 構成一覧画面
    path('parts-structure/', views.ProductList.as_view(),
         name='product_list'),   # 一覧
    path('parts-structure/search/', views.ProductList.as_view(),
         name='product_search'),   # 検索
    path('parts-structure/del/', views.product_del, name='product_del'),   # 削除

    # 構成を追加画面
    path('parts-structure/add/', views.parts_structure_edit,
         name='parts_structure_add'),  # 追加
    path('parts-structure/add/product/', views.parts_structure_add_product,
         name='parts_structure_add_product'),  # 製品挿入
    path('parts-structure/add/<int:product_id>/add/', views.parts_structure_edit_add,
         name='parts_structure_product_add'),  # 挿入
    path('parts-structure/add/<int:product_id>/addChildren/',
         views.parts_structure_edit_add_children,
         name='parts_structure_add_add_children'),  # 子の挿入
    path('parts-structure/add/<int:product_id>/mod/', views.parts_structure_edit_mod,
         name='parts_structure_add_mod'),  # 変更
    path('parts-structure/add/<int:product_id>/del/', views.parts_structure_edit_del,
         name='parts_structure_add_del'),  # 削除
    path('parts-structure/add/<int:product_id>/drop/', views.parts_structure_edit_drop,
         name='parts_structure_add_drop'),  # ドロップイベント
    path('parts-structure/add/<int:product_id>/undo/', views.parts_structure_edit_undo,
         name='parts_structure_add_undo'),  # 元に戻す
    path('parts-structure/add/<int:product_id>/redo/', views.parts_structure_edit_redo,
         name='parts_structure_add_redo'),  # やり直し

    # 構成を変更画面
    path('parts-structure/mod/<int:product_id>/', views.parts_structure_edit,
         name='parts_structure_mod'),  # 変更
    path('parts-structure/mod/<int:product_id>/add/', views.parts_structure_edit_add,
         name='parts_structure_mod_add'),  # 挿入
    path('parts-structure/mod/<int:product_id>/addChildren/',
         views.parts_structure_edit_add_children,
         name='parts_structure_mod_add_children'),  # 子の挿入
    path('parts-structure/mod/<int:product_id>/mod/', views.parts_structure_edit_mod,
         name='parts_structure_mod_mod'),  # 変更
    path('parts-structure/mod/<int:product_id>/del/', views.parts_structure_edit_del,
         name='parts_structure_mod_del'),  # 削除
    path('parts-structure/mod/<int:product_id>/drop/', views.parts_structure_edit_drop,
         name='parts_structure_mod_drop'),  # ドロップイベント
    path('parts-structure/mod/<int:product_id>/undo/', views.parts_structure_edit_undo,
         name='parts_structure_mod_undo'),  # 元に戻す
    path('parts-structure/mod/<int:product_id>/redo/', views.parts_structure_edit_redo,
         name='parts_structure_mod_redo'),  # やり直し
]

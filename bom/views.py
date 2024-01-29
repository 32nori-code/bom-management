from django.shortcuts import render
from django.views.generic.list import ListView
from django.db.models import Q
from bom.models import PartsStructure, Part, PartsStructureChangeSet, PartsStructureHistory, UndoRedoPointer
# from django.http import HttpRequest
from django.http import JsonResponse
from django.db.models import Max
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse


class ProductList(ListView):
    context_object_name = 'parts_structures'
    template_name = 'bom/parts_structure_list.html'
    paginate_by = 5  # １ページは最大5件ずつでページングする

    # def get(self, request, *args, **kwargs):
    #     parts_structures = PartsStructure.objects.filter(parent_id=None)
    #     self.object_list = parts_structures

    #     context = self.get_context_data(object_list=self.object_list)
    #     return self.render_to_response(context)

    def get_queryset(self):
        queryset = PartsStructure.objects.filter(parent_id=None)

        query = self.request.GET.get('query')
        if query is not None and query != '':
            queryset = queryset.filter(
                Q(part__name__icontains=query) |
                Q(part__code__icontains=query)
            )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('query', '')  # queryをcontextに追加
        return context


def parts_structure_edit(request, product_id=None):
    if product_id is None:
        nodes = None
        title = '構成を追加'
    else:
        # 実行
        nodes = find_by_product_id(product_id)
        title = '構成を変更'

    undo_status, redo_status = check_undo_redo(product_id)
    return render(request,
                  'bom/parts_structure_edit.html',   # 使用するテンプレート
                  {'product_id': product_id, 'nodes': nodes, 'undo': undo_status, 'redo': redo_status, 'title': title}
                  )


def get_children(id, quantity):
    parts_structures = PartsStructure.objects.filter(parent_id=id).order_by('sort')
    children = []
    for parts_structure in parts_structures:
        child = {
            'id': parts_structure.id,
            'code': parts_structure.part.code,
            'name': parts_structure.part.name,
            'quantity': parts_structure.quantity,
            'usedquantity': quantity * parts_structure.quantity,
            'children': get_children(parts_structure.id, quantity * parts_structure.quantity)
        }
        children.append(child)
    return children


# 変更画面の削除処理
def parts_structure_edit_del(request, product_id):
    current_parts_structure_id = request.GET.get("current_parts_structure_id")

    # エラーチェック
    if PartsStructure.objects.filter(pk=current_parts_structure_id).exists():
        exists = True
        # 実行
        with transaction.atomic():
            # product_idとcurrent_parts_structure_idが同じ場合の処理をこちらにかく。
            # elseの場合、下のロジックが動くように改める。
            current_parts_structure_id_int = int(current_parts_structure_id)
            if product_id == current_parts_structure_id_int:
                # 選択行のインスタンスを取得
                current_parts_structure = PartsStructure.objects.get(pk=current_parts_structure_id)
                # 選択された行のidの子を取得する。
                children_data = delete_childrens(current_parts_structure.id)
                # 取得された子のデータをフラットにしてならべる
                all_children = get_all_children(children_data)
                # 全ての子を削除する
                for child in all_children:
                    child_parts_structure = PartsStructure.objects.get(pk=child['id'])
                    child_parts_structure.delete()
                current_parts_structure.delete()
                return JsonResponse({"exists": exists})
            else:
                # undoRedoPointerの値よりPartsStructureChangeSet、PartsStructureHistoryの値を再更新する。
                update_history_from_pointer(product_id)
                # 新しい PartsStructureChangeSet インスタンスを作成
                parts_structure = PartsStructure.objects.get(id=product_id)
                parts_structure_change_set = PartsStructureChangeSet.objects.create(product=parts_structure)
                # 選択行のインスタンスを取得
                current_parts_structure = PartsStructure.objects.get(pk=current_parts_structure_id)
                # 選択された行のidの子を取得する。
                children_data = delete_childrens(current_parts_structure.id)
                # 取得された子のデータをフラットにしてならべる
                all_children = get_all_children(children_data)
                # 全ての子を削除する
                for child in all_children:
                    # PartsStructure.objects.get(pk=child['id']).delete()
                    child_parts_structure = PartsStructure.objects.get(pk=child['id'])
                    # child_parts_structure.delete()の実行後にHistoryに書き込むとpk(id)などの値がNoneとなってしまう
                    # 為、実行順序を1.Historyへの書き込み、2.child_parts_structure.delete()の実行へ変えました。
                    PartsStructureHistory.objects.create(
                        parts_structure_change_set=parts_structure_change_set,
                        parts_structure_original_id=child_parts_structure.id,
                        parent_original_id=child_parts_structure.parent_id,
                        sort=child_parts_structure.sort,
                        part=child_parts_structure.part,
                        quantity=child_parts_structure.quantity,
                        action='delete',
                        status='before'
                    )
                    child_parts_structure.delete()
                # current_parts_structure.delete()の実行後にHistoryに書き込むとpk(id)などの値が
                # Noneとなってしまう為、実行順序を1.Historyへの書き込み、2.parts_structure.delete()の
                # 実行へ変えました。
                PartsStructureHistory.objects.create(
                    parts_structure_change_set=parts_structure_change_set,
                    parts_structure_original_id=current_parts_structure.id,
                    parent_original_id=current_parts_structure.parent_id,
                    sort=current_parts_structure.sort,
                    part=current_parts_structure.part,
                    quantity=current_parts_structure.quantity,
                    action='delete',
                    status='before'
                )
                current_parts_structure.delete()

                # 指定したproductのUndoRedoPointerオブジェクトを取得
                pointer, created = UndoRedoPointer.objects.get_or_create(
                    product=parts_structure,
                    defaults={
                        'pointer': parts_structure_change_set
                    }
                )
                # すでに存在する場合は、pointer_idを更新
                if not created:
                    pointer.pointer = parts_structure_change_set
                    pointer.save()
                undo_status, redo_status = check_undo_redo(product_id)
                return JsonResponse({"exists": exists, 'undo': undo_status, 'redo': redo_status})
    else:
        exists = False
        return JsonResponse({"exists": exists})


# 削除対象のidを格納する。
def delete_childrens(id):
    child_parts_structures = PartsStructure.objects.filter(parent_id=id)
    children = []
    for child_parts_structure in child_parts_structures:
        child = {
            'id': child_parts_structure.id,
            'part_id': child_parts_structure.part_id,
            'children': delete_childrens(child_parts_structure.id)
        }
        children.append(child)
    return children


# 階層構造リストをフラットにする。
def get_all_children(data):
    all_children = []

    for item in data:
        all_children.append(item)
        all_children.extend(get_all_children(item['children']))

    return all_children


# TODO 追加画面の製品挿入処理
def parts_structure_add_product(request):
    edit_block_code = request.GET.get("edit_block_code")
    try:
        # エラーチェック
        if not Part.objects.filter(code=edit_block_code).exists():
            raise ValueError("存在しない製品が指定されました。")

        # 実行
        with transaction.atomic():
            # 製品の登録
            # new_parts_structure_instance = PartsStructure()
            # edit_block_code を適切な PartMaster インスタンスに変更する
            part_instance = Part.objects.get(code=edit_block_code)
            new_parts_structure_instance = PartsStructure()
            new_parts_structure_instance.parent_id = None
            new_parts_structure_instance.sort = 1
            new_parts_structure_instance.part = part_instance   # 正しい Part インスタンスを設定
            new_parts_structure_instance.quantity = None
            new_parts_structure_instance.save()

            parts_structure_change_set = PartsStructureChangeSet.objects.create(product=new_parts_structure_instance)

            PartsStructureHistory.objects.create(
                parts_structure_change_set=parts_structure_change_set,
                parts_structure_original_id=new_parts_structure_instance.id,
                parent_original_id=new_parts_structure_instance.parent_id,
                sort=new_parts_structure_instance.sort,
                part=new_parts_structure_instance.part,
                quantity=new_parts_structure_instance.quantity,
                action='create',
                status='after'
            )
            # 指定したproductのUndoRedoPointerオブジェクトを取得
            pointer, created = UndoRedoPointer.objects.get_or_create(
                product=new_parts_structure_instance,
                defaults={
                    'pointer': parts_structure_change_set
                }
            )
            # すでに存在する場合は、pointer_idを更新
            if not created:
                pointer.pointer = parts_structure_change_set
                pointer.save()
    except ValueError as e:
        # ここではエラーがキャッチされますが、
        # withブロック内で例外が発生した場合、
        # 自動的にロールバックされています。
        # print(f"トランザクションがロールバックされました: {e}")
        # return JsonResponse({"exists": False})
        return JsonResponse({"success": False, "message": str(e)})
    undo_status, redo_status = check_undo_redo(new_parts_structure_instance.id)
    return JsonResponse({"success": True,
                         "new_id": new_parts_structure_instance.id,
                         "name": part_instance.name, 'undo': undo_status,
                         "redo": redo_status})


# 変更画面の挿入処理
def parts_structure_edit_add(request, product_id):
    current_parts_structure_id = request.GET.get("current_parts_structure_id")
    edit_block_code = request.GET.get("edit_block_code")
    edit_block_quantity = request.GET.get("edit_block_quantity")
    try:
        # エラーチェック
        if not Part.objects.filter(code=edit_block_code).exists():
            raise ValueError("存在しない部品が指定されました。")
            # return JsonResponse({"exists": False})

        # 実行
        with transaction.atomic():
            # undoRedoPointerの値よりPartsStructureChangeSet、PartsStructureHistoryの値を再更新する。
            update_history_from_pointer(product_id)

            parts_structure = PartsStructure.objects.get(id=product_id)
            parts_structure_change_set = PartsStructureChangeSet.objects.create(
                product=parts_structure
            )

            current_parts_structure = PartsStructure.objects.get(
                pk=current_parts_structure_id
            )
            new_parts_structure_sort = current_parts_structure.sort
            # current_parts_structure.parent_idと同じ値かつ
            # current_parts_structure.part以上の値のインスタンスを取得
            change_sort_instances = PartsStructure.objects.filter(
                parent_id=current_parts_structure.parent_id,
                sort__gte=current_parts_structure.sort
            )
            # 取得したインスタンスの part_sort を更新して保存
            for instance in change_sort_instances:
                PartsStructureHistory.objects.create(
                    parts_structure_change_set=parts_structure_change_set,
                    parts_structure_original_id=instance.id,
                    parent_original_id=instance.parent_id,
                    sort=instance.sort,
                    part=instance.part,
                    quantity=instance.quantity,
                    action='update',
                    status='before'
                )
                instance.sort += 1
                instance.save()
                PartsStructureHistory.objects.create(
                    parts_structure_change_set=parts_structure_change_set,
                    parts_structure_original_id=instance.id,
                    parent_original_id=instance.parent_id,
                    sort=instance.sort,
                    part=instance.part,
                    quantity=instance.quantity,
                    action='update',
                    status='after'
                )

            # new_parts_structure_instance = PartsStructure()
            # edit_block_code を適切な PartMaster インスタンスに変更する
            part_instance = Part.objects.get(code=edit_block_code)
            new_parts_structure_instance = PartsStructure()
            # 正しい Part インスタンスを設定
            new_parts_structure_instance.part = part_instance
            new_parts_structure_instance.sort = new_parts_structure_sort
            new_parts_structure_instance.quantity = edit_block_quantity
            new_parts_structure_instance.parent_id = current_parts_structure.parent_id
            new_parts_structure_instance.save()
            PartsStructureHistory.objects.create(
                parts_structure_change_set=parts_structure_change_set,
                parts_structure_original_id=new_parts_structure_instance.id,
                parent_original_id=new_parts_structure_instance.parent_id,
                sort=new_parts_structure_instance.sort,
                part=new_parts_structure_instance.part,
                quantity=new_parts_structure_instance.quantity,
                action='create',
                status='after'
            )
            # 指定したproductのUndoRedoPointerオブジェクトを取得
            pointer, created = UndoRedoPointer.objects.get_or_create(
                product=parts_structure,
                defaults={
                    'pointer': parts_structure_change_set
                }
            )
            # すでに存在する場合は、pointer_idを更新
            if not created:
                pointer.pointer = parts_structure_change_set
                pointer.save()

            # 更新された値よりparts_structureに循環参照が発生しているか
            # 確認し発生していたら、ロールバックしてエラーメッセージを戻す。
            if check_for_cyclic_parts(product_id):
                raise ValueError("循環参照エラーが発生致しました。")

    except ValueError as e:
        # ここではエラーがキャッチされますが、
        # withブロック内で例外が発生した場合、
        # 自動的にロールバックされています。
        # print(f"トランザクションがロールバックされました: {e}")
        # return JsonResponse({"exists": False})
        return JsonResponse({"success": False, "message": str(e)})
    undo_status, redo_status = check_undo_redo(product_id)
    return JsonResponse({"success": True,
                         "new_id": new_parts_structure_instance.id,
                         "name": part_instance.name, "undo": undo_status,
                         "redo": redo_status})


# 変更画面の子の挿入処理
def parts_structure_edit_add_children(request, product_id):
    current_parts_structure_id = request.GET.get("current_parts_structure_id")
    edit_block_code = request.GET.get("edit_block_code")
    edit_block_quantity = request.GET.get("edit_block_quantity")
    try:
        # エラーチェック
        #  if Part.objects.filter(code=edit_block_code).exists():
        #     exists = True
        if not Part.objects.filter(code=edit_block_code).exists():
            raise ValueError("存在しない部品が指定されました。")
        # 実行
        with transaction.atomic():
            # undoRedoPointerの値よりPartsStructureChangeSet、PartsStructureHistoryの値を再更新する。
            update_history_from_pointer(product_id)
            # 新しい PartsStructureChangeSet インスタンスを作成
            parts_structure = PartsStructure.objects.get(id=product_id)
            parts_structure_change_set = PartsStructureChangeSet.objects.create(
                product=parts_structure
            )
            current_parts_structure = PartsStructure.objects.get(
                pk=current_parts_structure_id
            )
            # currentPartsStructure.id == parentのPartsStructure
            # かつその中で一番大きいsortの値を取得
            max_sort = PartsStructure.objects.filter(
                parent_id=current_parts_structure.id
            ).aggregate(Max('sort'))['sort__max']
            if max_sort is not None:
                new_parts_structure_sort = max_sort + 1
            else:
                new_parts_structure_sort = 1

            # edit_block_code を適切な Part インスタンスに変更する
            part_instance = Part.objects.get(code=edit_block_code)
            new_parts_structure_instance = PartsStructure()
            # 正しい Part インスタンスを設定
            new_parts_structure_instance.part = part_instance
            new_parts_structure_instance.sort = new_parts_structure_sort
            new_parts_structure_instance.quantity = edit_block_quantity
            # current_parts_structure.idに該当するPartsStructureインスタンスを取得してそれを設定
            # new_parts_structure_instance.parent_id = PartsStructure.objects.get(pk=int(current_parts_structure.id))
            # parent_instance = Part.objects.get(code=current_parts_structure)
            new_parts_structure_instance.parent_id = current_parts_structure.id
            # new_parts_structure_instance.parent = parent_instance
            new_parts_structure_instance.save()
            # aaa = PartsStructureHistory.objects.create(
            PartsStructureHistory.objects.create(
                parts_structure_change_set=parts_structure_change_set,
                parts_structure_original_id=new_parts_structure_instance.id,
                parent_original_id=new_parts_structure_instance.parent_id,
                sort=new_parts_structure_instance.sort,
                part=new_parts_structure_instance.part,
                quantity=new_parts_structure_instance.quantity,
                action='create',
                status='after'

            )
            # 指定したproductのUndoRedoPointerオブジェクトを取得
            pointer, created = UndoRedoPointer.objects.get_or_create(
                product=parts_structure,
                defaults={
                    'pointer': parts_structure_change_set
                }
            )
            # すでに存在する場合は、pointer_idを更新
            if not created:
                pointer.pointer = parts_structure_change_set
                pointer.save()

            # 更新された値よりparts_structureに循環参照が発生しているか
            # 確認し発生していたら、ロールバックしてエラーメッセージを戻す。
            if check_for_cyclic_parts(product_id):
                raise ValueError("循環参照エラーが発生致しました。")

    except ValueError as e:
        # ここではエラーがキャッチされますが、
        # withブロック内で例外が発生した場合、
        # 自動的にロールバックされています。
        # print(f"トランザクションがロールバックされました: {e}")
        # return JsonResponse({"exists": False})
        return JsonResponse({"success": False, "message": str(e)})

    undo_status, redo_status = check_undo_redo(product_id)
    return JsonResponse({"success": True,
                         "new_id": new_parts_structure_instance.id,
                         "name": part_instance.name,
                         "undo": undo_status,
                         "redo": redo_status
                         })


# 変更画面の変更処理
def parts_structure_edit_mod(request, product_id):
    current_parts_structure_id = request.GET.get("current_parts_structure_id")
    edit_block_code = request.GET.get("edit_block_code")
    edit_block_quantity = request.GET.get("edit_block_quantity")
    # エラーチェック
    if Part.objects.filter(code=edit_block_code).exists():
        exists = True
        # 実行
        with transaction.atomic():
            # undoRedoPointerの値よりPartsStructureChangeSet、PartsStructureHistoryの値を再更新する。
            update_history_from_pointer(product_id)
            # 新しい PartsStructureChangeSet インスタンスを作成
            parts_structure = PartsStructure.objects.get(id=product_id)
            parts_structure_change_set = PartsStructureChangeSet.objects.create(product=parts_structure)
            current_parts_structure = PartsStructure.objects.get(pk=current_parts_structure_id)
            PartsStructureHistory.objects.create(
                parts_structure_change_set=parts_structure_change_set,
                parts_structure_original_id=current_parts_structure.id,
                parent_original_id=current_parts_structure.parent_id,
                sort=current_parts_structure.sort,
                part=current_parts_structure.part,
                quantity=current_parts_structure.quantity,
                action='update',
                status='before'
            )
            current_parts_structure.quantity = edit_block_quantity
            current_parts_structure.save()
            PartsStructureHistory.objects.create(
                parts_structure_change_set=parts_structure_change_set,
                parts_structure_original_id=current_parts_structure.id,
                parent_original_id=current_parts_structure.parent_id,
                sort=current_parts_structure.sort,
                part=current_parts_structure.part,
                quantity=current_parts_structure.quantity,
                action='update',
                status='after'
            )
            # 指定したproductのUndoRedoPointerオブジェクトを取得
            pointer, created = UndoRedoPointer.objects.get_or_create(
                product=parts_structure,
                defaults={
                    'pointer': parts_structure_change_set
                }
            )
            # すでに存在する場合は、pointer_idを更新
            if not created:
                pointer.pointer = parts_structure_change_set
                pointer.save()
    else:
        exists = False
    undo_status, redo_status = check_undo_redo(product_id)
    return JsonResponse({"exists": exists, 'undo': undo_status, 'redo': redo_status})


# 変更画面のドロップイベント
def parts_structure_edit_drop(request, product_id):
    try:
        # 実行
        with transaction.atomic():
            update_history_from_pointer(product_id)
            # 新しい PartsStructureChangeSet インスタンスを作成
            parts_structure = PartsStructure.objects.get(id=product_id)
            parts_structure_change_set = PartsStructureChangeSet.objects.create(product=parts_structure)
            drop_target_id = request.GET.get("drop_target_id")    # 移動先のid
            insert_position = request.GET.get("insert_position")    # 移動先のidの前"before"、後"after"の情報
            dragged_id = request.GET.get("dragged_id")          # ドラッグした要素のid
            print('drop_target_id:', drop_target_id)
            print('insert_position:', insert_position)
            print('dragged_id:', dragged_id)
            # ドロップ先のインスタンスを取得
            drop_target_parts_structure = PartsStructure.objects.get(pk=drop_target_id)
            change_parts_structures = change_sorts(drop_target_parts_structure, insert_position, dragged_id)

            # ドロップ先の後ろのソートを書き換える
            for change_parts_structure in change_parts_structures:
                PartsStructureHistory.objects.create(
                    parts_structure_change_set=parts_structure_change_set,
                    parts_structure_original_id=change_parts_structure.id,
                    parent_original_id=change_parts_structure.parent_id,
                    sort=change_parts_structure.sort,
                    part=change_parts_structure.part,
                    quantity=change_parts_structure.quantity,
                    action='update',
                    status='before'
                )
                change_parts_structure.sort += 1
                change_parts_structure.save()
                PartsStructureHistory.objects.create(
                    parts_structure_change_set=parts_structure_change_set,
                    parts_structure_original_id=change_parts_structure.id,
                    parent_original_id=change_parts_structure.parent_id,
                    sort=change_parts_structure.sort,
                    part=change_parts_structure.part,
                    quantity=change_parts_structure.quantity,
                    action='update',
                    status='after'
                )
            # 移動元のparent,sortを書き換える
            dragged_parts_structure = PartsStructure.objects.get(pk=dragged_id)
            PartsStructureHistory.objects.create(
                parts_structure_change_set=parts_structure_change_set,
                parts_structure_original_id=dragged_parts_structure.id,
                parent_original_id=dragged_parts_structure.parent_id,
                sort=dragged_parts_structure.sort,
                part=dragged_parts_structure.part,
                quantity=dragged_parts_structure.quantity,
                action='update',
                status='before'
            )
            dragged_parts_structure.parent_id = drop_target_parts_structure.parent_id
            if insert_position == 'before':
                dragged_parts_structure.sort = drop_target_parts_structure.sort
            else:
                dragged_parts_structure.sort = drop_target_parts_structure.sort + 1
            dragged_parts_structure.save()
            PartsStructureHistory.objects.create(
                parts_structure_change_set=parts_structure_change_set,
                parts_structure_original_id=dragged_parts_structure.id,
                parent_original_id=dragged_parts_structure.parent_id,
                sort=dragged_parts_structure.sort,
                part=dragged_parts_structure.part,
                quantity=dragged_parts_structure.quantity,
                action='update',
                status='after'
            )
            # 指定したproductのUndoRedoPointerオブジェクトを取得
            pointer, created = UndoRedoPointer.objects.get_or_create(
                product=parts_structure,
                defaults={
                    'pointer': parts_structure_change_set
                }
            )
            # すでに存在する場合は、pointer_idを更新
            if not created:
                pointer.pointer = parts_structure_change_set
                pointer.save()
            # 更新された値よりparts_structureに循環参照が発生しているか
            # 確認し発生していたら、ロールバックしてエラーメッセージを戻す。
            if check_for_cyclic_parts(product_id):
                raise ValueError("循環参照エラーが発生致しました。")
    except ValueError as e:
        # ここではエラーがキャッチされますが、
        # withブロック内で例外が発生した場合、
        # 自動的にロールバックされています。
        # print(f"トランザクションがロールバックされました: {e}")
        return JsonResponse({"success": False, "message": str(e)})

    undo_status, redo_status = check_undo_redo(product_id)
    # return JsonResponse({"exists": exists, 'undo': undo_status, 'redo': redo_status})
    return JsonResponse({"success": True,
                         "undo": undo_status,
                         "redo": redo_status})


# ソート変更対象のidを格納する。
def change_sorts(drop_target_parts_structure, insert_position, dragged_id):
    if insert_position == 'before':
        change_parts_structures = PartsStructure.objects.filter(parent_id=drop_target_parts_structure.parent_id,
                                                         sort__gte=drop_target_parts_structure.sort
                                                         ).exclude(id=dragged_id)
    else:
        change_parts_structures = PartsStructure.objects.filter(parent_id=drop_target_parts_structure.parent_id,
                                                         sort__gt=drop_target_parts_structure.sort
                                                         ).exclude(id=dragged_id)
    return change_parts_structures


# 変更画面の「元に戻す」ボタン処理
def parts_structure_edit_undo(request, product_id):
    # 実行
    with transaction.atomic():
        try:
            undo_redo_pointer = UndoRedoPointer.objects.get(product=product_id)
            # undo_redo_pointer.pointerのトランザクション処理を打ち消す。
            parts_structure_historys = PartsStructureHistory.objects.filter(parts_structure_change_set=undo_redo_pointer.pointer).order_by('-pk')
            for parts_structure_history in parts_structure_historys:
                # 作成
                if parts_structure_history.action == 'create':
                    parts_structure_to_delete = PartsStructure.objects.get(pk=parts_structure_history.parts_structure_original_id)
                    parts_structure_to_delete.delete()
                # 更新
                if parts_structure_history.action == 'update' and parts_structure_history.status == 'before':
                    parts_structure_to_update = PartsStructure.objects.get(pk=parts_structure_history.parts_structure_original_id)
                    parts_structure_to_update.parent_id = parts_structure_history.parent_original_id
                    parts_structure_to_update.sort = parts_structure_history.sort
                    parts_structure_to_update.part = parts_structure_history.part
                    parts_structure_to_update.quantity = parts_structure_history.quantity
                    parts_structure_to_update.save()
                # 削除
                if parts_structure_history.action == 'delete':
                    PartsStructure.objects.create(
                        # historyのidから戻さないと整合性が取れない。
                        id=parts_structure_history.parts_structure_original_id,
                        parent_id=parts_structure_history.parent_original_id,
                        sort=parts_structure_history.sort,
                        part=parts_structure_history.part,
                        quantity=parts_structure_history.quantity,
                    )
            # 現状のポインタを１つ前のポインタへ戻す。
            parts_structure = PartsStructure.objects.get(pk=product_id)
            parts_structure_change_set = PartsStructureChangeSet.objects.filter(
                product=parts_structure, pk__lt=undo_redo_pointer.pointer.id
            ).order_by('-pk').first()
            # parts_structure_change_setが取れなければundo_redo_pointerを削除。
            if parts_structure_change_set is None:
                undo_redo_pointer.delete()
            else:
                undo_redo_pointer.pointer = parts_structure_change_set
                undo_redo_pointer.save()
        except UndoRedoPointer.DoesNotExist:
            pass
        # 再描画の為のデータを取り出す。
        nodes = find_by_product_id(product_id)
        undo_status, redo_status = check_undo_redo(product_id)
    return render(request,
                  'bom/parts_structure_edit.html',   # 使用するテンプレート
                  {'product_id': product_id, 'nodes': nodes, 'undo': undo_status, 'redo': redo_status}
                  )


# 変更画面の「やり直し」ボタン処理
def parts_structure_edit_redo(request, product_id):
    # 実行
    with transaction.atomic():
        try:
            undo_redo_pointer = UndoRedoPointer.objects.get(product=product_id)
            # undo_redo_pointer.pointerのトランザクション処理を打ち消すを打ち消す。
            # parts_structure_historys = PartsStructureHistory.objects.filter(parts_structure_change_set=undo_redo_pointer.pointer).order_by('-pk')
            # pointerより大きい最初の１件を取り出す。
            parts_structure = PartsStructure.objects.get(pk=product_id)
            change_set = PartsStructureChangeSet.objects.filter(
                product=parts_structure, pk__gt=undo_redo_pointer.pointer.id
            ).order_by('pk').first()
            redo_execute(change_set)
            # 現状のポインタを１つ後のポインタへ進める。
            parts_structure = PartsStructure.objects.get(pk=product_id)
            parts_structure_change_set = PartsStructureChangeSet.objects.filter(
                product=parts_structure, pk__gt=undo_redo_pointer.pointer.id
            ).order_by('pk').first()
            # parts_structure_change_setが取れない時はここの関数はそもそも呼ばれない。
            if parts_structure_change_set is None:
                pass
            else:
                undo_redo_pointer.pointer = parts_structure_change_set
                undo_redo_pointer.save()
        except UndoRedoPointer.DoesNotExist:
            # undo_redo_pointerにレコードが存在しなくかつparts_structure_change_set
            # に値が存在する場合、一番若いidの１件のchange_setよりredo処理を実行する。
            parts_structure = PartsStructure.objects.get(pk=product_id)
            change_set = PartsStructureChangeSet.objects.filter(
                product=parts_structure
            ).order_by('pk').first()
            redo_execute(change_set)
            # 現状のポインタを１つ後のポインタへ進める。
            parts_structure = PartsStructure.objects.get(pk=product_id)
            parts_structure_change_set = PartsStructureChangeSet.objects.filter(
                product=parts_structure
            ).order_by('pk').first()
            # parts_structure_change_setが取れない時はここの関数はそもそも呼ばれない。
            if parts_structure_change_set is None:
                pass
            else:
                UndoRedoPointer.objects.create(
                    product=parts_structure,
                    pointer=parts_structure_change_set
                )
        # 再描画の為のデータを取り出す。
        nodes = find_by_product_id(product_id)
        # nodes = []
        # parts_structure = PartsStructure.objects.get(pk=product_id)
        # quantity = 1
        # usedquantity = 1
        # dict_data = {
        #     'id': parts_structure.id,
        #     'code': parts_structure.part.code,
        #     'name': parts_structure.part.name,
        #     'quantity': quantity,
        #     'usedquantity': usedquantity,
        #     'children': get_children(parts_structure.id, quantity)
        # }
        # nodes.append(dict_data)
        undo_status, redo_status = check_undo_redo(product_id)
    return render(request,
                  'bom/parts_structure_edit.html',   # 使用するテンプレート
                  {'product_id': product_id, 'nodes': nodes, 'undo': undo_status, 'redo': redo_status}
                  )


def redo_execute(change_set):
    parts_structure_historys = PartsStructureHistory.objects.filter(parts_structure_change_set=change_set).order_by('pk')
    for parts_structure_history in parts_structure_historys:
        # 作成
        if parts_structure_history.action == 'create':
            PartsStructure.objects.create(
                # historyのidから戻さないと整合性が取れない。
                id=parts_structure_history.parts_structure_original_id,
                parent_id=parts_structure_history.parent_original_id,
                sort=parts_structure_history.sort,
                part=parts_structure_history.part,
                quantity=parts_structure_history.quantity,
            )
        # 更新
        if parts_structure_history.action == 'update' and parts_structure_history.status == 'after':
            parts_structure_to_update = PartsStructure.objects.get(pk=parts_structure_history.parts_structure_original_id)
            parts_structure_to_update.parent_id = parts_structure_history.parent_original_id
            parts_structure_to_update.sort = parts_structure_history.sort
            parts_structure_to_update.part = parts_structure_history.part
            parts_structure_to_update.quantity = parts_structure_history.quantity
            parts_structure_to_update.save()
        # 削除
        if parts_structure_history.action == 'delete':
            parts_structure_to_delete = PartsStructure.objects.get(pk=parts_structure_history.parts_structure_original_id)
            parts_structure_to_delete.delete()


# undoRedoPointerの値よりPartsStructureChangeSet、PartsStructureHistoryの値を再更新する。
def update_history_from_pointer(product_id):
    # ポインタより大きな値のPartsStructureChangeSet、PartsStructureHistoryインスタンスがあればそちらは削除する。
    # その後、新しいPartsStructureChangeSet、PartsStructureHistoryインスタンスを追加する。
    try:
        undo_redo_pointer = UndoRedoPointer.objects.get(product=product_id)
        parts_structure_change_sets = PartsStructureChangeSet.objects.filter(
            product=undo_redo_pointer.product,
            id__gt=undo_redo_pointer.pointer.id
        )
        for change_set in parts_structure_change_sets:
            # 以下はForeignKeyでparts_structure_change_setつながっているのであえて削除しなくても
            # parts_structure_change_setが削除されるとこちらも消えるはず。
            # PartsStructureHistory.objects.filter(parts_structure_change_set=change_set).delete()
            change_set.delete()
    except UndoRedoPointer.DoesNotExist:
        # UndoRedoPointerが存在しないけれどもPartsStructureChangeSet、PartsStructureHistoryが存在する場合
        # PartsStructureChangeSet、PartsStructureHistoryを削除する。
        parts_structure = PartsStructure.objects.get(id=product_id)
        parts_structure_change_sets = PartsStructureChangeSet.objects.filter(
            product=parts_structure
        )
        for change_set in parts_structure_change_sets:
            # 以下はForeignKeyでparts_structure_change_setつながっているのであえて削除しなくても
            # parts_structure_change_setが削除されるとこちらも消えるはず。
            # PartsStructureHistory.objects.filter(parts_structure_change_set=change_set).delete()
            change_set.delete()


def check_undo_redo(product_id):
    if product_id is None:
        undo = False
        redo = False
    else:
        # product_idよりUndoRedoPointerを参照
        # データが存在する場合、undo変数をTrue
        # データが存在しない場合、undo変数をFalse
        # データが存在しかつpointerより大きい値のPartsStructureChangeSetのidが存在する場合、redo変数をTrueにする。
        # データが存在しかつpointerより大きい値のPartsStructureChangeSetのidが存在しない場合、redo変数をFalseにする。
        # データが存在しないかつPartsStructureChangeSetが存在する場合、redo変数をTrueにする。
        # データが存在しないかつPartsStructureChangeSetが存在しない場合、redo変数をFalseにする。
        parts_structure = PartsStructure.objects.get(pk=product_id)
        try:
            undo_redo_pointer = UndoRedoPointer.objects.get(product=parts_structure)
            undo = True
            entries = PartsStructureChangeSet.objects.filter(product=parts_structure, pk__gt=undo_redo_pointer.pointer.id)
            if entries.exists():
                redo = True
            else:
                redo = False
        except UndoRedoPointer.DoesNotExist:
            undo = False
            entries = PartsStructureChangeSet.objects.filter(product=parts_structure)
            if entries.exists():
                redo = True
            else:
                redo = False

    return undo, redo


def find_by_product_id(product_id):
    nodes = []
    parts_structure = PartsStructure.objects.get(pk=product_id)
    quantity = 1
    usedquantity = 1
    dict_data = {
        'id': parts_structure.id,
        'code': parts_structure.part.code,
        'name': parts_structure.part.name,
        'quantity': quantity,
        'usedquantity': usedquantity,
        'children': get_children(parts_structure.id, quantity)
    }
    nodes.append(dict_data)
    return nodes


# 一覧画面の削除処理
def product_del(request):
    # GETパラメータから selectedIds を取得
    selected_ids_str = request.GET.get('selectedIds', '')
    # 実行
    with transaction.atomic():
        # カンマで区切られた文字列をリストに変換
        selected_ids_list = selected_ids_str.split(',') if selected_ids_str else []
        # 選択されたIDのリストをループして処理
        for id_str in selected_ids_list:
            # 選択行のインスタンスを取得
            current_parts_structure = PartsStructure.objects.get(pk=id_str)
            # 選択された行のidの子を取得する。
            children_data = delete_childrens(current_parts_structure.id)
            # 取得された子のデータをフラットにしてならべる
            all_children = get_all_children(children_data)
            # 全ての子を削除する
            for child in all_children:
                child_parts_structure = PartsStructure.objects.get(pk=child['id'])
                child_parts_structure.delete()
            current_parts_structure.delete()
    # ProductListビューにリダイレクト
    return HttpResponseRedirect(reverse('bom:product_list'))


def is_cyclic_part(id, part_id, visited_parts):
    """
    部品の循環参照をチェックするためのヘルパー関数
    :param id: 現在調べているPartsStructureオブジェクトのID
    :param part_id: 現在調べている部品のID
    :param visited_parts: これまでに訪れた部品のIDのセット
    :return: 循環が存在する場合はTrue、それ以外はFalse
    """
    if part_id in visited_parts:
        return True  # 現在の部品が以前に訪れた部品のリストに存在する場合、循環参照が存在する

    visited_parts.add(part_id)

    # 現在の部品の子部品をチェック
    parts_structures = PartsStructure.objects.filter(parent_id=id).order_by('sort')
    for parts_structure in parts_structures:
        if is_cyclic_part(parts_structure.id, parts_structure.part.id, visited_parts):
            return True

    visited_parts.remove(part_id)
    return False


def check_for_cyclic_parts(product_id):
    """
    指定された製品IDについて部品の循環参照をチェックする
    :param product_id: 製品ID
    :return: 循環が存在する場合はTrue、それ以外はFalse
    """
    parts_structure = PartsStructure.objects.get(pk=product_id)
    return is_cyclic_part(parts_structure.id, parts_structure.part.id, set())

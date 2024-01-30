# bom-management
- 昔から部品表のサンプルをネット上で検索していましがた見かける事がなかったので
自分で作ってみようと思い立ちました。お役立ちになるか分かりませんが動くものをつくりましたのでよろしければお使い下さい。
# 始め方
以下の手順に従って、ローカル環境でプロジェクトをセットアップし、実行できます。
# 前提条件
- Python 3.11.3
※恐らく、こちらのバージョンに限らず動くかとは思います。
# インストール方法

## 1.リポジトリのクローン
GitHubからプロジェクトをクローンします。
```powershell
git clone https://github.com/32nori-code/bom-management.git bom_management
cd bom_management
```

## 2.依存関係のインストール
必要なライブラリと依存関係をインストールします。
```powershell
pip install -r requirements.txt
```

## 3.データベースのセットアップ
データベースマイグレーションを実行します。
```powershell
python manage.py migrate
python manage.py loaddata part_list_app/fixtures/part_data.json
```
part_dataの中に製品、部品のコードが入っています。
入力確認時こちらを利用下さい。

## 4.サーバーの起動
Django開発サーバーを起動します。
```powershell
python manage.py runserver
```
サーバーが起動したら、ブラウザで http://127.0.0.1:8000/part-list-app/composition/ にアクセスしてプロジェクトを表示します。

# 使用方法
プロジェクトの初期画面として「構成一覧」画面が表示されます。追加ボタンを押して、製品を登録、部品を登録して下さい。基本右クリックにて挿入、子の挿入、変更、削除などの画面が表示されます。登録してみて下さい。部品などは、ドラッグ＆ドロップ操作にて移動出来ます。
製品の登録がされましたらトップ画面に構成一覧が表示されます。右クリックにて製品の削除もできます。undo(元に戻す),redo(やり直し)アイコンも設けましたので操作を間違った際フォローしてくれると思います。

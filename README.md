### 目錄結構說明

```
├── requirements.txt    # Python相依套件。會用於部署至Google Cloud Function。
├── src/                # 放金融商品資料下載、分析 推薦的功能。會用於部署至Google Cloud Function。
├── main.py             # Google Cloud Function 版本的的進入函數。
├── app.py              # WebUI 版本的進入函數。
├── utils/              # 放置 WebUI所需的PyThon擴充功能。
├── templates/          # 放各個頁面，使用 HTML 定義瀏覽器顯示的內容與結構
│   └── index.htm
└── static/             # 放功能元件，支援頁面的美觀與互動
    ├── css/            # 樣式元件，使用 CSS 控制頁面的顏色、字型、排版
    ├── js/             # 互動元件，使用 JavaScript 控制按鈕、輸入框、表單等操作
    └── img/
```
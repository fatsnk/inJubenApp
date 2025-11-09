package com.example.injubenapp

import androidx.appcompat.app.AppCompatActivity
import android.os.Bundle
import android.content.ContentValues
import android.content.Context
import android.os.Build
import android.os.Environment
import android.print.PrintManager
import android.provider.MediaStore
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import com.google.android.material.bottomnavigation.BottomNavigationView
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlin.concurrent.thread
import java.io.File
import java.io.FileOutputStream
import java.io.IOException

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var bottomNavigationView: BottomNavigationView
    private var editorContent: String? = null
    private var currentPage = "editor" // "editor" or "preview"

    inner class WebAppInterface {
        @JavascriptInterface
        fun downloadPdf(base64: String, fileName: String) {
            try {
                val contentValues = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, fileName)
                    put(MediaStore.MediaColumns.MIME_TYPE, "application/pdf")
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                        put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                    }
                }

                val resolver = contentResolver
                val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, contentValues)

                if (uri != null) {
                    val pdfBytes = Base64.decode(base64, Base64.DEFAULT)
                    resolver.openOutputStream(uri).use { outputStream ->
                        outputStream?.write(pdfBytes)
                    }
                    runOnUiThread {
                        Toast.makeText(this@MainActivity, "已保存到“下载”文件夹", Toast.LENGTH_LONG).show()
                    }
                } else {
                    throw IOException("Failed to create new MediaStore record.")
                }
            } catch (e: Exception) {
                e.printStackTrace()
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "保存失败: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }

        @JavascriptInterface
        fun downloadTxt(content: String, fileName: String) {
            try {
                val contentValues = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, fileName)
                    put(MediaStore.MediaColumns.MIME_TYPE, "text/plain")
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                        put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                    }
                }

                val resolver = contentResolver
                val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, contentValues)

                if (uri != null) {
                    resolver.openOutputStream(uri).use { outputStream ->
                        outputStream?.write(content.toByteArray())
                    }
                    runOnUiThread {
                        Toast.makeText(this@MainActivity, "已保存到“下载”文件夹", Toast.LENGTH_LONG).show()
                    }
                } else {
                    throw IOException("Failed to create new MediaStore record.")
                }
            } catch (e: Exception) {
                e.printStackTrace()
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "保存失败: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }

        @JavascriptInterface
        fun print() {
            runOnUiThread {
                try {
                    val printManager = getSystemService(Context.PRINT_SERVICE) as PrintManager
                    val jobName = "Fountain Document"
                    val printAdapter = webView.createPrintDocumentAdapter(jobName)
                    printManager.print(jobName, printAdapter, null)
                } catch (e: android.content.ActivityNotFoundException) {
                    Toast.makeText(this@MainActivity, "无法启动打印服务。请确保您的设备上已安装并启用了打印服务。", Toast.LENGTH_LONG).show()
                } catch (e: Exception) {
                    Toast.makeText(this@MainActivity, "打印失败: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webview)
        webView.settings.javaScriptEnabled = true // Enable JavaScript for Flask app
        webView.addJavascriptInterface(WebAppInterface(), "Android")

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                editorContent?.let {
                    val script = when (currentPage) {
                        "editor" -> "setEditorText(`$it`);"
                        "preview" -> "setFountainText(`$it`);"
                        else -> ""
                    }
                    webView.evaluateJavascript(script, null)
                }
            }
        }

        bottomNavigationView = findViewById(R.id.bottom_navigation)
        bottomNavigationView.setOnNavigationItemSelectedListener { item ->
            val scriptToRun = when (currentPage) {
                "editor" -> "getEditorText()"
                "preview" -> "getFountainText()"
                else -> ""
            }

            // Add a short delay to ensure WebView is ready
            Thread.sleep(100)
            webView.evaluateJavascript(scriptToRun) { content ->
                // The result from JS is a JSON string, so we need to unquote it.
                val text = content?.trim('"')?.replace("\\n", "\n")?.replace("\\'", "'")
                editorContent = if (text == "null") "" else text

                when (item.itemId) {
                    R.id.nav_editor -> {
                        currentPage = "editor"
                        webView.loadUrl("http://127.0.0.1:5021")
                        true
                    }
                    R.id.nav_preview -> {
                        currentPage = "preview"
                        webView.loadUrl("http://127.0.0.1:5021/preview")
                        true
                    }
                    else -> false
                }
            }
            true
        }


        // 复制字体文件到缓存
        copyAssetToCache("juben/fonts/SourceHanSerifSC-Light.ttf")
        copyAssetToCache("juben/fonts/SourceHanSansSC-Medium.ttf")
        copyAssetToCache("juben/fonts/SourceHanSansSC-Regular.ttf")

        startPython()
        startFlask()

        // 在加载 URL 之前添加一个短暂的延迟，以确保 Flask 服务器有足够的时间启动
        Thread.sleep(3000) // 延迟 2 秒
        runOnUiThread {
            webView.loadUrl("http://127.0.0.1:5021")
        }
    }

    private fun startPython() {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
    }

    private fun startFlask() {
        val fontsPath = cacheDir.absolutePath
        thread {
            val py = Python.getInstance()
            val mainModule = py.getModule("main")
            mainModule.callAttr("main", fontsPath)
        }
    }

    private fun copyAssetToCache(assetPath: String) {
        val outFile = File(cacheDir, File(assetPath).name)
        if (outFile.exists()) {
            // 如果文件已存在，可以跳过复制
            return
        }
        try {
            assets.open(assetPath).use { inputStream ->
                FileOutputStream(outFile).use { outputStream ->
                    inputStream.copyTo(outputStream)
                }
            }
        } catch (e: IOException) {
            e.printStackTrace()
        }
    }
}
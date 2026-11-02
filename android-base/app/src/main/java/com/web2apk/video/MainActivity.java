package com.web2apk.video;

import android.app.AlertDialog;
import android.app.DownloadManager;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PictureInPictureParams;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.RelativeLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class MainActivity extends android.app.Activity {
    private static final String TAG = "Web2Apk";
    private static final String CHANNEL_ID = "web2apk";

    private WebView webView;
    private ProgressBar progressBar;
    private RelativeLayout rootLayout;
    private FrameLayout fullscreenContainer;
    private LinearLayout toolbar;
    private TextView tipText;

    private View customView;
    private WebChromeClient.CustomViewCallback customViewCallback;
    private AudioManager audioManager;
    private GestureDetector gestureDetector;

    private Config config;
    private final Set<String> blockedHosts = new HashSet<>();
    private final List<String> mediaUrls = new ArrayList<>();
    private boolean inPip = false;
    private boolean videoSeen = false;

    private final Handler tipHandler = new Handler(Looper.getMainLooper());
    private final Runnable hideTip = () -> { if (tipText != null) tipText.setVisibility(View.GONE); };

    // 用于接收下载完成的广播（仅做提示）
    private final BroadcastReceiver dlReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (DownloadManager.ACTION_DOWNLOAD_COMPLETE.equals(intent.getAction())) {
                Toast.makeText(context, "视频下载完成，可在「下载」目录查看", Toast.LENGTH_SHORT).show();
            }
        }
    };

    private static class Config {
        String startUrl = "https://www.bilibili.com";
        String uaMode = "mobile";
        String customUserAgent = "";
        boolean fullscreenGesture = true;
        boolean pip = true;
        boolean backgroundAudio = true;
        boolean adBlock = true;
        boolean videoDownload = true;
        String themeColor = "#1f6feb";
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        config = loadConfig();
        applyTheme();
        createNotificationChannel();
        setContentView(R.layout.activity_main);

        audioManager = (AudioManager) getSystemService(AUDIO_SERVICE);
        loadBlocklist();
        initViews();
        initWebView();

        IntentFilter f = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        registerReceiver(dlReceiver, f);
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            if (nm != null && nm.getNotificationChannel(CHANNEL_ID) == null) {
                NotificationChannel ch = new NotificationChannel(
                        CHANNEL_ID, "Web2Apk 后台播放", NotificationManager.IMPORTANCE_LOW);
                ch.setDescription("用于后台/小窗继续播放视频声音");
                nm.createNotificationChannel(ch);
            }
        }
    }

    private void applyTheme() {
        try {
            int c = Color.parseColor(config.themeColor);
            if (Build.VERSION.SDK_INT >= 21) {
                getWindow().setStatusBarColor(c);
                getWindow().setNavigationBarColor(c);
            }
        } catch (Exception e) {
            Log.w(TAG, "theme color parse fail", e);
        }
    }

    private void initViews() {
        rootLayout = findViewById(R.id.root);
        webView = findViewById(R.id.webview);
        progressBar = findViewById(R.id.progress);
        toolbar = findViewById(R.id.toolbar);
        fullscreenContainer = findViewById(R.id.fullscreen_container);
        tipText = findViewById(R.id.tip_text);

        findViewById(R.id.btn_back).setOnClickListener(v -> goBack());
        findViewById(R.id.btn_forward).setOnClickListener(v -> goForward());
        findViewById(R.id.btn_refresh).setOnClickListener(v -> webView.reload());
        findViewById(R.id.btn_home).setOnClickListener(v -> webView.loadUrl(config.startUrl));
        findViewById(R.id.btn_download).setOnClickListener(v -> showDownloadDialog());
    }

    private void initWebView() {
        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setDatabaseEnabled(true);
        ws.setLoadWithOverviewMode(true);
        ws.setUseWideViewPort(true);
        ws.setMediaPlaybackRequiresUserGesture(false);
        ws.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        ws.setCacheMode(WebSettings.LOAD_DEFAULT);
        ws.setAppCacheEnabled(true);
        ws.setAppCachePath(getApplicationContext().getCacheDir().getAbsolutePath());
        ws.setAllowFileAccess(false);
        ws.setJavaScriptCanOpenWindowsAutomatically(false);
        try { ws.setOffscreenPreRaster(true); } catch (Exception ignore) {}

        applyUserAgent(ws);

        if (config.fullscreenGesture) {
            gestureDetector = makeGestureDetector();
        }

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return false; // 始终在站内打开，不跳系统浏览器
            }

            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (config.adBlock && isBlocked(uri)) {
                    return new WebResourceResponse("text/plain", "utf-8",
                            new ByteArrayInputStream(new byte[0]));
                }
                if (config.videoDownload && looksLikeMedia(uri.toString())) {
                    String u = uri.toString();
                    synchronized (mediaUrls) {
                        if (!mediaUrls.contains(u)) mediaUrls.add(u);
                    }
                }
                return null;
            }

            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                progressBar.setVisibility(View.VISIBLE);
                progressBar.setProgress(0);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progressBar.setVisibility(View.GONE);
                injectVideoSniffer(view);
            }

            @Override
            public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                progressBar.setVisibility(View.GONE);
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progressBar.setProgress(newProgress);
            }

            @Override
            public void onShowCustomView(View view, CustomViewCallback cb) {
                showCustomView(view, cb);
            }

            @Override
            public void onHideCustomView() {
                hideCustomView();
            }

            @Override
            public boolean onCreateWindow(WebView view, boolean isDialog, boolean isUserGesture, android.os.Message resultMsg) {
                // 拦截弹窗：绝大多数视频站弹窗是广告
                return false;
            }
        });

        // JS 桥：页面里的 <video> 把地址回传给原生，用于「下载」
        webView.addJavascriptInterface(new Object() {
            @android.webkit.JavascriptInterface
            public void onVideoFound(String url) {
                if (url != null && !url.isEmpty()) {
                    synchronized (mediaUrls) {
                        if (!mediaUrls.contains(url)) {
                            mediaUrls.add(url);
                            videoSeen = true;
                        }
                    }
                }
            }
        }, "Web2ApkSniffer");

        webView.loadUrl(config.startUrl);
    }

    private void applyUserAgent(WebSettings ws) {
        if ("desktop".equals(config.uaMode)) {
            ws.setUserAgentString("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    + "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36");
        } else if ("custom".equals(config.uaMode) && !config.customUserAgent.isEmpty()) {
            ws.setUserAgentString(config.customUserAgent);
        }
        // mobile 使用系统默认 UA
    }

    private void injectVideoSniffer(WebView view) {
        if (!config.videoDownload) return;
        String js = "(function(){"
                + "var vs=document.getElementsByTagName('video');"
                + "for(var i=0;i<vs.length;i++){"
                + "  var s=vs[i].src||vs[i].currentSrc; if(s) Web2ApkSniffer.onVideoFound(s);"
                + "  var srcs=vs[i].querySelectorAll('source');"
                + "  for(var j=0;j<srcs.length;j++){ if(srcs[j].src) Web2ApkSniffer.onVideoFound(srcs[j].src); }"
                + "}"
                + "})();";
        view.loadUrl("javascript:" + js);
    }

    private void showCustomView(View view, WebChromeClient.CustomViewCallback cb) {
        customView = view;
        customViewCallback = cb;
        fullscreenContainer.setVisibility(View.VISIBLE);
        fullscreenContainer.addView(view, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        toolbar.setVisibility(View.GONE);
        videoSeen = true;
        if (Build.VERSION.SDK_INT >= 19) {
            getWindow().getDecorView().setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION);
        }
        if (config.fullscreenGesture && gestureDetector != null) {
            fullscreenContainer.setOnTouchListener((v, ev) -> gestureDetector.onTouchEvent(ev));
        }
    }

    private void hideCustomView() {
        if (customView == null) return;
        fullscreenContainer.setVisibility(View.GONE);
        fullscreenContainer.removeView(customView);
        customView = null;
        fullscreenContainer.setOnTouchListener(null);
        toolbar.setVisibility(View.VISIBLE);
        if (Build.VERSION.SDK_INT >= 19) {
            getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_VISIBLE);
        }
        if (customViewCallback != null) customViewCallback.onCustomViewHidden();
        customViewCallback = null;
    }

    private GestureDetector makeGestureDetector() {
        return new GestureDetector(this, new GestureDetector.SimpleOnGestureListener() {
            private float startX, startY;
            private boolean horiz = false, vert = false;
            private int startVol;
            private float startBri;

            @Override
            public boolean onDown(MotionEvent e) {
                startX = e.getX();
                startY = e.getY();
                horiz = false;
                vert = false;
                startVol = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC);
                WindowManager.LayoutParams lp = getWindow().getAttributes();
                startBri = (lp.screenBrightness >= 0) ? lp.screenBrightness : 0.5f;
                return true;
            }

            @Override
            public boolean onScroll(MotionEvent e1, MotionEvent e2, float dx, float dy) {
                float absX = Math.abs(e2.getX() - startX);
                float absY = Math.abs(e2.getY() - startY);
                if (!horiz && !vert) {
                    if (absX > absY && absX > 24) horiz = true;
                    else if (absY > absX && absY > 24) vert = true;
                }
                if (horiz) {
                    float h = getResources().getDisplayMetrics().heightPixels;
                    float delta = -(e2.getY() - startY) / h;
                    float bri = Math.max(0f, Math.min(1f, startBri + delta * 1.6f));
                    WindowManager.LayoutParams lp = getWindow().getAttributes();
                    lp.screenBrightness = bri;
                    getWindow().setAttributes(lp);
                    showTip("亮度 " + (int) (bri * 100) + "%");
                } else if (vert) {
                    int maxVol = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
                    float h = getResources().getDisplayMetrics().heightPixels;
                    float delta = -(e2.getY() - startY) / h;
                    int vol = Math.max(0, Math.min(maxVol, (int) (startVol + delta * maxVol * 1.6f)));
                    audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, vol, 0);
                    showTip("音量 " + (int) ((float) vol / maxVol * 100) + "%");
                }
                return true;
            }
        });
    }

    private void showTip(String t) {
        tipText.setText(t);
        tipText.setVisibility(View.VISIBLE);
        tipHandler.removeCallbacks(hideTip);
        tipHandler.postDelayed(hideTip, 800);
    }

    private void goBack() {
        if (customView != null) { hideCustomView(); return; }
        if (webView.canGoBack()) webView.goBack();
        else finish();
    }

    private void goForward() {
        if (webView.canGoForward()) webView.goForward();
    }

    private void showDownloadDialog() {
        synchronized (mediaUrls) {
            if (mediaUrls.isEmpty()) {
                Toast.makeText(this, "还没检测到视频，先播放一下再试", Toast.LENGTH_SHORT).show();
                return;
            }
            final String[] items = mediaUrls.toArray(new String[0]);
            new AlertDialog.Builder(this)
                    .setTitle("选择要下载的视频")
                    .setItems(items, (d, which) -> downloadUrl(items[which]))
                    .setNegativeButton("取消", null)
                    .show();
        }
    }

    private void downloadUrl(String url) {
        try {
            DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            DownloadManager.Request r = new DownloadManager.Request(Uri.parse(url));
            r.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            String name = Uri.parse(url).getLastPathSegment();
            if (name == null || !name.contains(".")) name = "video_" + System.currentTimeMillis() + ".mp4";
            r.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "Web2Apk/" + name);
            dm.enqueue(r);
            Toast.makeText(this, "已开始下载：" + name, Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Toast.makeText(this, "下载失败：" + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    public void onUserLeaveHint() {
        super.onUserLeaveHint();
        if (config.pip && Build.VERSION.SDK_INT >= 26 && videoSeen) {
            try {
                if (customView != null) hideCustomView();
                PictureInPictureParams p = new PictureInPictureParams.Builder().build();
                enterPictureInPictureMode(p);
            } catch (Exception e) {
                Log.w(TAG, "pip enter fail", e);
            }
        }
    }

    @Override
    public void onPictureInPictureModeChanged(boolean isInPictureInPictureMode, android.content.res.Configuration newConfig) {
        super.onPictureInPictureModeChanged(isInPictureInPictureMode, newConfig);
        inPip = isInPictureInPictureMode;
        if (isInPictureInPictureMode) {
            toolbar.setVisibility(View.GONE);
            progressBar.setVisibility(View.GONE);
        } else {
            toolbar.setVisibility(customView != null ? View.GONE : View.VISIBLE);
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (config.backgroundAudio && !inPip && videoSeen) {
            startKeepAlive();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        stopKeepAlive();
    }

    @Override
    protected void onDestroy() {
        stopKeepAlive();
        try { unregisterReceiver(dlReceiver); } catch (Exception ignore) {}
        if (webView != null) {
            webView.clearHistory();
            webView.destroy();
        }
        super.onDestroy();
    }

    private void startKeepAlive() {
        try {
            Intent i = new Intent(this, KeepAliveService.class);
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(i);
            else startService(i);
        } catch (Exception e) {
            Log.w(TAG, "keepalive start fail", e);
        }
    }

    private void stopKeepAlive() {
        try { stopService(new Intent(this, KeepAliveService.class)); } catch (Exception ignore) {}
    }

    @Override
    public void onBackPressed() {
        if (customView != null) { hideCustomView(); return; }
        if (webView.canGoBack()) { webView.goBack(); return; }
        super.onBackPressed();
    }

    // ---------- 配置与拦截 ----------

    private Config loadConfig() {
        Config c = new Config();
        try {
            InputStream is = getAssets().open("config.json");
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[1024];
            int n;
            while ((n = is.read(buf)) > 0) bos.write(buf, 0, n);
            is.close();
            JSONObject o = new JSONObject(new String(bos.toByteArray(), StandardCharsets.UTF_8));
            if (o.has("startUrl")) c.startUrl = o.getString("startUrl");
            if (o.has("uaMode")) c.uaMode = o.getString("uaMode");
            if (o.has("customUserAgent")) c.customUserAgent = o.getString("customUserAgent");
            if (o.has("themeColor")) c.themeColor = o.getString("themeColor");
            if (o.has("features")) {
                JSONObject f = o.getJSONObject("features");
                c.fullscreenGesture = f.optBoolean("fullscreenGesture", true);
                c.pip = f.optBoolean("pip", true);
                c.backgroundAudio = f.optBoolean("backgroundAudio", true);
                c.adBlock = f.optBoolean("adBlock", true);
                c.videoDownload = f.optBoolean("videoDownload", true);
            }
        } catch (Exception e) {
            Log.w(TAG, "config load fail", e);
        }
        return c;
    }

    private void loadBlocklist() {
        try {
            BufferedReader r = new BufferedReader(new InputStreamReader(getAssets().open("adblock.txt")));
            String line;
            while ((line = r.readLine()) != null) {
                line = line.trim().toLowerCase();
                if (!line.isEmpty() && !line.startsWith("#")) blockedHosts.add(line);
            }
            r.close();
        } catch (Exception e) {
            Log.w(TAG, "blocklist load fail", e);
        }
    }

    private boolean isBlocked(Uri uri) {
        String host = uri.getHost();
        if (host == null) return false;
        host = host.toLowerCase();
        for (String b : blockedHosts) {
            if (host.equals(b) || host.endsWith("." + b)) return true;
        }
        return false;
    }

    private boolean looksLikeMedia(String url) {
        String u = url.toLowerCase();
        return u.contains(".mp4") || u.contains(".m3u8") || u.contains(".webm")
                || u.contains(".m4v") || u.contains(".ts?") || u.contains(".mpd")
                || u.contains("manifest") && u.contains("format");
    }
}

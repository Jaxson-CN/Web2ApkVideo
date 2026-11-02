package com.web2apk.video;

import android.app.Notification;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

/**
 * 后台/小窗播放时拉起的前台服务，用一条常驻通知把进程优先级提起来，
 * 让 WebView 的视频声音在退出应用后仍能继续播放。属于「尽力而为」实现，
 * 部分机型/视频站策略可能仍会暂停。
 */
public class KeepAliveService extends Service {
    private static final int NOTIF_ID = 1001;

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (Build.VERSION.SDK_INT >= 26) {
            Notification n = new Notification.Builder(this, "web2apk")
                    .setContentTitle("后台播放中")
                    .setContentText("点击返回应用 · Web2Apk")
                    .setSmallIcon(android.R.drawable.ic_media_play)
                    .setOngoing(true)
                    .build();
            startForeground(NOTIF_ID, n);
        }
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}

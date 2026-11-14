.class public Lcom/thomatelot/mh3unotebook/MainActivity;
.super Landroid/app/Activity;
.source "MainActivity.smali"

# The whole app is the page in assets/ shown in a WebView. This activity only adds
# what a page cannot do on its own: save / open files with Android's file picker
# (Google Drive, Downloads...) and Android's back button.


# instance fields
.field public web:Landroid/webkit/WebView;

.field public pending:Ljava/lang/String;

.field public opened:Ljava/lang/String;


# direct methods
.method public constructor <init>()V
    .registers 1

    invoke-direct {p0}, Landroid/app/Activity;-><init>()V

    return-void
.end method


# virtual methods
.method protected onCreate(Landroid/os/Bundle;)V
    .registers 5

    invoke-super {p0, p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V

    new-instance v0, Landroid/webkit/WebView;

    invoke-direct {v0, p0}, Landroid/webkit/WebView;-><init>(Landroid/content/Context;)V

    iput-object v0, p0, Lcom/thomatelot/mh3unotebook/MainActivity;->web:Landroid/webkit/WebView;

    invoke-virtual {v0}, Landroid/webkit/WebView;->getSettings()Landroid/webkit/WebSettings;

    move-result-object v1

    const/4 v2, 0x1

    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setJavaScriptEnabled(Z)V

    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setDomStorageEnabled(Z)V

    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setAllowFileAccess(Z)V

    new-instance v1, Lcom/thomatelot/mh3unotebook/Bridge;

    invoke-direct {v1, p0}, Lcom/thomatelot/mh3unotebook/Bridge;-><init>(Lcom/thomatelot/mh3unotebook/MainActivity;)V

    const-string v2, "Android"

    invoke-virtual {v0, v1, v2}, Landroid/webkit/WebView;->addJavascriptInterface(Ljava/lang/Object;Ljava/lang/String;)V

    invoke-virtual {p0, v0}, Landroid/app/Activity;->setContentView(Landroid/view/View;)V

    const-string v1, "file:///android_asset/index.html"

    invoke-virtual {v0, v1}, Landroid/webkit/WebView;->loadUrl(Ljava/lang/String;)V

    return-void
.end method

.method public onBackPressed()V
    .registers 2

    iget-object v0, p0, Lcom/thomatelot/mh3unotebook/MainActivity;->web:Landroid/webkit/WebView;

    if-eqz v0, :cond_super

    invoke-virtual {v0}, Landroid/webkit/WebView;->canGoBack()Z

    move-result v0

    if-eqz v0, :cond_super

    iget-object v0, p0, Lcom/thomatelot/mh3unotebook/MainActivity;->web:Landroid/webkit/WebView;

    invoke-virtual {v0}, Landroid/webkit/WebView;->goBack()V

    return-void

    :cond_super
    invoke-super {p0}, Landroid/app/Activity;->onBackPressed()V

    return-void
.end method

# Tells the page what happened: window.nativeEvent('saved' | 'opened' | 'cancel' | 'error').
.method public tell(Ljava/lang/String;)V
    .registers 5

    new-instance v0, Ljava/lang/StringBuilder;

    const-string v1, "window.nativeEvent && window.nativeEvent('"

    invoke-direct {v0, v1}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    invoke-virtual {v0, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    const-string v1, "')"

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    iget-object v1, p0, Lcom/thomatelot/mh3unotebook/MainActivity;->web:Landroid/webkit/WebView;

    const/4 v2, 0x0

    invoke-virtual {v1, v0, v2}, Landroid/webkit/WebView;->evaluateJavascript(Ljava/lang/String;Landroid/webkit/ValueCallback;)V

    return-void
.end method

# Request 1: the user chose where to save "pending". Request 2: the user chose a file to open.
.method protected onActivityResult(IILandroid/content/Intent;)V
    .registers 10

    invoke-super {p0, p1, p2, p3}, Landroid/app/Activity;->onActivityResult(IILandroid/content/Intent;)V

    const/4 v0, -0x1

    if-ne p2, v0, :cond_cancel

    if-eqz p3, :cond_cancel

    invoke-virtual {p3}, Landroid/content/Intent;->getData()Landroid/net/Uri;

    move-result-object v0

    if-eqz v0, :cond_cancel

    :try_start
    invoke-virtual {p0}, Landroid/app/Activity;->getContentResolver()Landroid/content/ContentResolver;

    move-result-object v1

    const/4 v2, 0x1

    if-ne p1, v2, :cond_open

    invoke-virtual {v1, v0}, Landroid/content/ContentResolver;->openOutputStream(Landroid/net/Uri;)Ljava/io/OutputStream;

    move-result-object v2

    iget-object v3, p0, Lcom/thomatelot/mh3unotebook/MainActivity;->pending:Ljava/lang/String;

    const-string v4, "UTF-8"

    invoke-virtual {v3, v4}, Ljava/lang/String;->getBytes(Ljava/lang/String;)[B

    move-result-object v3

    invoke-virtual {v2, v3}, Ljava/io/OutputStream;->write([B)V

    invoke-virtual {v2}, Ljava/io/OutputStream;->close()V

    const/4 v2, 0x0

    iput-object v2, p0, Lcom/thomatelot/mh3unotebook/MainActivity;->pending:Ljava/lang/String;

    const-string v2, "saved"

    invoke-virtual {p0, v2}, Lcom/thomatelot/mh3unotebook/MainActivity;->tell(Ljava/lang/String;)V

    return-void

    :cond_open
    const/4 v2, 0x2

    if-ne p1, v2, :cond_cancel

    invoke-virtual {v1, v0}, Landroid/content/ContentResolver;->openInputStream(Landroid/net/Uri;)Ljava/io/InputStream;

    move-result-object v1

    new-instance v2, Ljava/io/ByteArrayOutputStream;

    invoke-direct {v2}, Ljava/io/ByteArrayOutputStream;-><init>()V

    const/16 v3, 0x2000

    new-array v3, v3, [B

    :goto_read
    invoke-virtual {v1, v3}, Ljava/io/InputStream;->read([B)I

    move-result v4

    if-ltz v4, :cond_done

    const/4 v5, 0x0

    invoke-virtual {v2, v3, v5, v4}, Ljava/io/ByteArrayOutputStream;->write([BII)V

    goto :goto_read

    :cond_done
    invoke-virtual {v1}, Ljava/io/InputStream;->close()V

    const-string v3, "UTF-8"

    invoke-virtual {v2, v3}, Ljava/io/ByteArrayOutputStream;->toString(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v2

    iput-object v2, p0, Lcom/thomatelot/mh3unotebook/MainActivity;->opened:Ljava/lang/String;

    const-string v2, "opened"

    invoke-virtual {p0, v2}, Lcom/thomatelot/mh3unotebook/MainActivity;->tell(Ljava/lang/String;)V

    return-void
    :try_end
    .catch Ljava/lang/Exception; {:try_start .. :try_end} :catch_error

    :cond_cancel
    const-string v0, "cancel"

    invoke-virtual {p0, v0}, Lcom/thomatelot/mh3unotebook/MainActivity;->tell(Ljava/lang/String;)V

    return-void

    :catch_error
    move-exception v0

    const-string v0, "error"

    invoke-virtual {p0, v0}, Lcom/thomatelot/mh3unotebook/MainActivity;->tell(Ljava/lang/String;)V

    return-void
.end method

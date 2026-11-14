.class public Lcom/thomatelot/mh3unotebook/Bridge;
.super Ljava/lang/Object;
.source "Bridge.smali"

# The page's window.Android object.


# instance fields
.field private final act:Lcom/thomatelot/mh3unotebook/MainActivity;


# direct methods
.method public constructor <init>(Lcom/thomatelot/mh3unotebook/MainActivity;)V
    .registers 2

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    iput-object p1, p0, Lcom/thomatelot/mh3unotebook/Bridge;->act:Lcom/thomatelot/mh3unotebook/MainActivity;

    return-void
.end method


# virtual methods
.method public version()Ljava/lang/String;
    .registers 2
    .annotation runtime Landroid/webkit/JavascriptInterface;
    .end annotation

    const-string v0, "1.0.0"

    return-object v0
.end method

# Asks where to save the file (Android's "Save to" picker: Downloads, Google Drive...).
.method public saveFile(Ljava/lang/String;Ljava/lang/String;)V
    .registers 7
    .annotation runtime Landroid/webkit/JavascriptInterface;
    .end annotation

    iget-object v0, p0, Lcom/thomatelot/mh3unotebook/Bridge;->act:Lcom/thomatelot/mh3unotebook/MainActivity;

    iput-object p2, v0, Lcom/thomatelot/mh3unotebook/MainActivity;->pending:Ljava/lang/String;

    new-instance v1, Landroid/content/Intent;

    const-string v2, "android.intent.action.CREATE_DOCUMENT"

    invoke-direct {v1, v2}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V

    const-string v2, "android.intent.category.OPENABLE"

    invoke-virtual {v1, v2}, Landroid/content/Intent;->addCategory(Ljava/lang/String;)Landroid/content/Intent;

    const-string v2, "application/octet-stream"

    invoke-virtual {v1, v2}, Landroid/content/Intent;->setType(Ljava/lang/String;)Landroid/content/Intent;

    const-string v2, "android.intent.extra.TITLE"

    invoke-virtual {v1, v2, p1}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;

    new-instance v2, Lcom/thomatelot/mh3unotebook/Starter;

    const/4 v3, 0x1

    invoke-direct {v2, v0, v1, v3}, Lcom/thomatelot/mh3unotebook/Starter;-><init>(Lcom/thomatelot/mh3unotebook/MainActivity;Landroid/content/Intent;I)V

    invoke-virtual {v0, v2}, Landroid/app/Activity;->runOnUiThread(Ljava/lang/Runnable;)V

    return-void
.end method

# Asks which file to open; the page then reads it with takeOpened().
.method public openFile()V
    .registers 5
    .annotation runtime Landroid/webkit/JavascriptInterface;
    .end annotation

    iget-object v0, p0, Lcom/thomatelot/mh3unotebook/Bridge;->act:Lcom/thomatelot/mh3unotebook/MainActivity;

    new-instance v1, Landroid/content/Intent;

    const-string v2, "android.intent.action.OPEN_DOCUMENT"

    invoke-direct {v1, v2}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V

    const-string v2, "android.intent.category.OPENABLE"

    invoke-virtual {v1, v2}, Landroid/content/Intent;->addCategory(Ljava/lang/String;)Landroid/content/Intent;

    const-string v2, "*/*"

    invoke-virtual {v1, v2}, Landroid/content/Intent;->setType(Ljava/lang/String;)Landroid/content/Intent;

    new-instance v2, Lcom/thomatelot/mh3unotebook/Starter;

    const/4 v3, 0x2

    invoke-direct {v2, v0, v1, v3}, Lcom/thomatelot/mh3unotebook/Starter;-><init>(Lcom/thomatelot/mh3unotebook/MainActivity;Landroid/content/Intent;I)V

    invoke-virtual {v0, v2}, Landroid/app/Activity;->runOnUiThread(Ljava/lang/Runnable;)V

    return-void
.end method

.method public takeOpened()Ljava/lang/String;
    .registers 4
    .annotation runtime Landroid/webkit/JavascriptInterface;
    .end annotation

    iget-object v0, p0, Lcom/thomatelot/mh3unotebook/Bridge;->act:Lcom/thomatelot/mh3unotebook/MainActivity;

    iget-object v1, v0, Lcom/thomatelot/mh3unotebook/MainActivity;->opened:Ljava/lang/String;

    const/4 v2, 0x0

    iput-object v2, v0, Lcom/thomatelot/mh3unotebook/MainActivity;->opened:Ljava/lang/String;

    return-object v1
.end method

# Writes the file in the app's cache and opens Android's share sheet (Drive, Gmail, Quick Share...).
.method public shareFile(Ljava/lang/String;Ljava/lang/String;)Z
    .registers 9
    .annotation runtime Landroid/webkit/JavascriptInterface;
    .end annotation

    :try_start
    iget-object v0, p0, Lcom/thomatelot/mh3unotebook/Bridge;->act:Lcom/thomatelot/mh3unotebook/MainActivity;

    new-instance v1, Ljava/io/File;

    invoke-virtual {v0}, Landroid/content/Context;->getCacheDir()Ljava/io/File;

    move-result-object v2

    const-string v3, "share"

    invoke-direct {v1, v2, v3}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-virtual {v1}, Ljava/io/File;->mkdirs()Z

    new-instance v2, Ljava/io/File;

    invoke-direct {v2, v1, p1}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    new-instance v3, Ljava/io/FileOutputStream;

    invoke-direct {v3, v2}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V

    const-string v4, "UTF-8"

    invoke-virtual {p2, v4}, Ljava/lang/String;->getBytes(Ljava/lang/String;)[B

    move-result-object v4

    invoke-virtual {v3, v4}, Ljava/io/FileOutputStream;->write([B)V

    invoke-virtual {v3}, Ljava/io/FileOutputStream;->close()V

    new-instance v3, Ljava/lang/StringBuilder;

    const-string v4, "content://com.thomatelot.mh3unotebook.files/"

    invoke-direct {v3, v4}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    invoke-static {p1}, Landroid/net/Uri;->encode(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v4

    invoke-virtual {v3, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v3}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v3

    invoke-static {v3}, Landroid/net/Uri;->parse(Ljava/lang/String;)Landroid/net/Uri;

    move-result-object v3

    new-instance v4, Landroid/content/Intent;

    const-string v5, "android.intent.action.SEND"

    invoke-direct {v4, v5}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V

    const-string v5, "application/octet-stream"

    invoke-virtual {v4, v5}, Landroid/content/Intent;->setType(Ljava/lang/String;)Landroid/content/Intent;

    const-string v5, "android.intent.extra.STREAM"

    invoke-virtual {v4, v5, v3}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Landroid/os/Parcelable;)Landroid/content/Intent;

    const-string v5, "android.intent.extra.SUBJECT"

    invoke-virtual {v4, v5, p1}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;

    const/4 v5, 0x1

    invoke-virtual {v4, v5}, Landroid/content/Intent;->addFlags(I)Landroid/content/Intent;

    const/4 v5, 0x0

    invoke-static {v4, v5}, Landroid/content/Intent;->createChooser(Landroid/content/Intent;Ljava/lang/CharSequence;)Landroid/content/Intent;

    move-result-object v4

    new-instance v5, Lcom/thomatelot/mh3unotebook/Starter;

    const/4 v1, 0x0

    invoke-direct {v5, v0, v4, v1}, Lcom/thomatelot/mh3unotebook/Starter;-><init>(Lcom/thomatelot/mh3unotebook/MainActivity;Landroid/content/Intent;I)V

    invoke-virtual {v0, v5}, Landroid/app/Activity;->runOnUiThread(Ljava/lang/Runnable;)V

    const/4 v0, 0x1

    return v0
    :try_end
    .catch Ljava/lang/Exception; {:try_start .. :try_end} :catch_error

    :catch_error
    move-exception v0

    const/4 v0, 0x0

    return v0
.end method

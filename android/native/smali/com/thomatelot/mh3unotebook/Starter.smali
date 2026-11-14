.class public Lcom/thomatelot/mh3unotebook/Starter;
.super Ljava/lang/Object;
.source "Starter.smali"

# interfaces
.implements Ljava/lang/Runnable;

# Starts an intent on the UI thread (the page's calls arrive on another thread).
# code 0: plain startActivity (share sheet); otherwise startActivityForResult.


# instance fields
.field private final act:Lcom/thomatelot/mh3unotebook/MainActivity;

.field private final intent:Landroid/content/Intent;

.field private final code:I


# direct methods
.method public constructor <init>(Lcom/thomatelot/mh3unotebook/MainActivity;Landroid/content/Intent;I)V
    .registers 4

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    iput-object p1, p0, Lcom/thomatelot/mh3unotebook/Starter;->act:Lcom/thomatelot/mh3unotebook/MainActivity;

    iput-object p2, p0, Lcom/thomatelot/mh3unotebook/Starter;->intent:Landroid/content/Intent;

    iput p3, p0, Lcom/thomatelot/mh3unotebook/Starter;->code:I

    return-void
.end method


# virtual methods
.method public run()V
    .registers 4

    :try_start
    iget-object v0, p0, Lcom/thomatelot/mh3unotebook/Starter;->act:Lcom/thomatelot/mh3unotebook/MainActivity;

    iget-object v1, p0, Lcom/thomatelot/mh3unotebook/Starter;->intent:Landroid/content/Intent;

    iget v2, p0, Lcom/thomatelot/mh3unotebook/Starter;->code:I

    if-nez v2, :cond_result

    invoke-virtual {v0, v1}, Landroid/app/Activity;->startActivity(Landroid/content/Intent;)V

    return-void

    :cond_result
    invoke-virtual {v0, v1, v2}, Landroid/app/Activity;->startActivityForResult(Landroid/content/Intent;I)V

    return-void
    :try_end
    .catch Ljava/lang/Exception; {:try_start .. :try_end} :catch_error

    :catch_error
    move-exception v0

    iget-object v0, p0, Lcom/thomatelot/mh3unotebook/Starter;->act:Lcom/thomatelot/mh3unotebook/MainActivity;

    const-string v1, "error"

    invoke-virtual {v0, v1}, Lcom/thomatelot/mh3unotebook/MainActivity;->tell(Ljava/lang/String;)V

    return-void
.end method

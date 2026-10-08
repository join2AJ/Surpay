# kotlinx.serialization
-keepattributes *Annotation*, InnerClasses, Signature, Exceptions
-keepclassmembers @kotlinx.serialization.Serializable class com.surpay.app.** {
    *** Companion;
    kotlinx.serialization.KSerializer serializer(...);
}
# Retrofit service interfaces
-keep,allowobfuscation interface com.surpay.app.data.SurpayApi
-keep,allowobfuscation,allowshrinking class kotlin.coroutines.Continuation
-keep,allowobfuscation,allowshrinking interface retrofit2.Call
-keep,allowobfuscation,allowshrinking class retrofit2.Response

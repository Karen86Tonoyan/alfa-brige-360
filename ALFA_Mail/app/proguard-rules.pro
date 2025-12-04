# ALFA Mail ProGuard Rules

# Keep JavaMail classes
-keep class javax.mail.** { *; }
-keep class com.sun.mail.** { *; }
-dontwarn javax.mail.**
-dontwarn com.sun.mail.**

# Keep activation framework
-keep class javax.activation.** { *; }
-dontwarn javax.activation.**

# Keep model classes if using serialization
-keepattributes Signature
-keepattributes *Annotation*

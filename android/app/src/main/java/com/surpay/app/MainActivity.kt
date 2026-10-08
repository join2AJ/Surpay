package com.surpay.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.Surface
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.surpay.app.data.AppPrefs
import com.surpay.app.data.ServerStore
import com.surpay.app.data.SurpayApi
import com.surpay.app.data.SurpayRepository
import com.surpay.app.data.TokenStore
import com.surpay.app.data.deviceInfo
import com.surpay.app.ui.SurpayApp
import com.surpay.app.ui.SurpayViewModel
import com.surpay.app.ui.theme.SurpayTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val tokens = TokenStore(applicationContext)
        val server = ServerStore(applicationContext, BuildConfig.API_BASE_URL)
        val api = SurpayApi.create({ server.current }, { tokens.cached }, deviceInfo(applicationContext, BuildConfig.VERSION_NAME))
        // Installed over an older version (rather than fresh): show "what's new" once.
        val pkg = packageManager.getPackageInfo(packageName, 0)
        val isUpdate = pkg.lastUpdateTime > pkg.firstInstallTime
        val factory = viewModelFactory {
            initializer {
                SurpayViewModel(SurpayRepository(api, tokens), server, AppPrefs(applicationContext),
                    BuildConfig.VERSION_CODE, isUpdate)
            }
        }
        val vm = ViewModelProvider(this, factory)[SurpayViewModel::class.java]

        setContent {
            SurpayTheme {
                Surface { SurpayApp(vm) }
            }
        }
    }
}

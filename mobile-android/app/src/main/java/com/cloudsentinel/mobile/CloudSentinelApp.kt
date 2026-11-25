package com.cloudsentinel.mobile

import android.app.Application
import com.cloudsentinel.mobile.core.security.SecureSessionStore
import com.cloudsentinel.mobile.data.repository.AlertRepository
import com.cloudsentinel.mobile.service.NotificationChannels

class CloudSentinelApp : Application() {

    lateinit var sessionStore: SecureSessionStore
        private set

    lateinit var repository: AlertRepository
        private set

    override fun onCreate() {
        super.onCreate()
        NotificationChannels.register(this)
        sessionStore = SecureSessionStore(this)
        repository = AlertRepository(sessionStore)
    }
}

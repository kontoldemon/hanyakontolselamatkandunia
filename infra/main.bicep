targetScope = 'resourceGroup'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Public admin IP in CIDR form, for example 203.0.113.10/32.')
param adminIpCidr string

@description('SSH public key for the admin user on both VMs.')
param adminSshPublicKey string

@description('VM size for the sensor.')
param sensorVmSize string = 'Standard_B2ats_v2'

@description('VM size for the private ClickHouse VM.')
param clickHouseVmSize string = 'Standard_B2s'

@description('Admin username for SSH.')
param adminUsername string = 'azureuser'

@description('Sensor data disk size in GB.')
param sensorDataDiskSizeGB int = 64

@description('ClickHouse data disk size in GB.')
param clickHouseDataDiskSizeGB int = 64

@secure()
@description('Optional LLM provider key. Stored in Key Vault when supplied.')
param llmApiKey string = ''

@secure()
@description('ClickHouse default-user password. Must match the value passed to deploy.sh.')
param clickHousePassword string

var prefix = 'cloudsentinel'
var vnetName = '${prefix}-vnet'
var sensorSubnetName = 'sensor'
var dataSubnetName = 'data'
var privateEndpointSubnetName = 'privateEndpoints'
var sensorSubnetCidr = '10.20.1.0/24'
var dataSubnetCidr = '10.20.2.0/24'
var privateEndpointSubnetCidr = '10.20.3.0/24'
var sensorSubnetId = resourceId('Microsoft.Network/virtualNetworks/subnets', vnetName, sensorSubnetName)
var dataSubnetId = resourceId('Microsoft.Network/virtualNetworks/subnets', vnetName, dataSubnetName)
var privateEndpointSubnetId = resourceId('Microsoft.Network/virtualNetworks/subnets', vnetName, privateEndpointSubnetName)
var sensorNsgName = '${prefix}-sensor-nsg'
var dataNsgName = '${prefix}-data-nsg'
var sensorPublicIpName = '${prefix}-sensor-pip'
var sensorNicName = '${prefix}-sensor-nic'
var sensorVmName = '${prefix}-sensor'
var clickHouseNicName = '${prefix}-clickhouse-nic'
var clickHouseVmName = '${prefix}-clickhouse'
var storageName = 'cs${uniqueString(resourceGroup().id)}'
var backupContainerName = 'backups'
var unblockQueueName = 'cloudsentinel-unblock'
var keyVaultName = 'cs-kv-${uniqueString(resourceGroup().id)}'
var eventGridTopicName = '${prefix}-blocks'
var functionPlanName = '${prefix}-plan'
var functionAppName = 'cs-fn-${uniqueString(resourceGroup().id)}'
var logAnalyticsName = 'cs-logs-${uniqueString(resourceGroup().id)}'
var appInsightsName = 'cs-appi-${uniqueString(resourceGroup().id)}'

resource sensorNsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: sensorNsgName
  location: location
  properties: {
    securityRules: [
      {
        name: 'Allow-Honeypot-SSH'
        properties: {
          priority: 200
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '22'
          sourceAddressPrefix: 'Internet'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'Allow-HTTPS'
        properties: {
          priority: 210
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: 'Internet'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'Allow-HTTP-ACME'
        properties: {
          priority: 220
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '80'
          sourceAddressPrefix: 'Internet'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'Allow-Management-SSH'
        properties: {
          priority: 230
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '22222'
          sourceAddressPrefix: adminIpCidr
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'Deny-Inbound'
        properties: {
          priority: 4096
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

resource dataNsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: dataNsgName
  location: location
  properties: {
    securityRules: [
      {
        name: 'Allow-ClickHouse-HTTP-From-Sensor'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '8123'
          sourceAddressPrefix: sensorSubnetCidr
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'Allow-ClickHouse-Native-From-Sensor'
        properties: {
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '9000'
          sourceAddressPrefix: sensorSubnetCidr
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'Allow-SSH-From-Sensor'
        properties: {
          priority: 120
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '22'
          sourceAddressPrefix: sensorSubnetCidr
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'Deny-Inbound'
        properties: {
          priority: 4096
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.20.0.0/16'
      ]
    }
    subnets: [
      {
        name: sensorSubnetName
        properties: {
          addressPrefix: sensorSubnetCidr
          networkSecurityGroup: {
            id: sensorNsg.id
          }
        }
      }
      {
        name: dataSubnetName
        properties: {
          addressPrefix: dataSubnetCidr
          networkSecurityGroup: {
            id: dataNsg.id
          }
        }
      }
      {
        name: privateEndpointSubnetName
        properties: {
          addressPrefix: privateEndpointSubnetCidr
        }
      }
    ]
  }
}

resource sensorPublicIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: sensorPublicIpName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
    dnsSettings: {
      domainNameLabel: '${prefix}-${uniqueString(resourceGroup().id)}'
    }
  }
}

resource sensorNic 'Microsoft.Network/networkInterfaces@2024-05-01' = {
  name: sensorNicName
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          subnet: {
            id: sensorSubnetId
          }
          publicIPAddress: {
            id: sensorPublicIp.id
          }
        }
      }
    ]
    networkSecurityGroup: {
      id: sensorNsg.id
    }
  }
  dependsOn: [
    vnet
  ]
}

resource clickHouseNic 'Microsoft.Network/networkInterfaces@2024-05-01' = {
  name: clickHouseNicName
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          subnet: {
            id: dataSubnetId
          }
        }
      }
    ]
    networkSecurityGroup: {
      id: dataNsg.id
    }
  }
  dependsOn: [
    vnet
  ]
}

resource sensorVm 'Microsoft.Compute/virtualMachines@2024-07-01' = {
  name: sensorVmName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    hardwareProfile: {
      vmSize: sensorVmSize
    }
    osProfile: {
      computerName: sensorVmName
      adminUsername: adminUsername
      linuxConfiguration: {
        disablePasswordAuthentication: true
        ssh: {
          publicKeys: [
            {
              path: '/home/${adminUsername}/.ssh/authorized_keys'
              keyData: adminSshPublicKey
            }
          ]
        }
      }
      customData: base64(loadTextContent('sensor-cloud-init.sh'))
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'ubuntu-24_04-lts'
        sku: 'server'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: 'StandardSSD_LRS'
        }
        deleteOption: 'Delete'
      }
      dataDisks: [
        {
          lun: 0
          name: '${sensorVmName}-data'
          createOption: 'Empty'
          diskSizeGB: sensorDataDiskSizeGB
          managedDisk: {
            storageAccountType: 'StandardSSD_LRS'
          }
          deleteOption: 'Delete'
        }
      ]
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: sensorNic.id
        }
      ]
    }
  }
  dependsOn: [
    sensorNic
  ]
}

resource clickHouseVm 'Microsoft.Compute/virtualMachines@2024-07-01' = {
  name: clickHouseVmName
  location: location
  properties: {
    hardwareProfile: {
      vmSize: clickHouseVmSize
    }
    osProfile: {
      computerName: clickHouseVmName
      adminUsername: adminUsername
      linuxConfiguration: {
        disablePasswordAuthentication: true
        ssh: {
          publicKeys: [
            {
              path: '/home/${adminUsername}/.ssh/authorized_keys'
              keyData: adminSshPublicKey
            }
          ]
        }
      }
      customData: base64(replace(loadTextContent('clickhouse-cloud-init.sh'), '__CLICKHOUSE_PASSWORD__', clickHousePassword))
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'ubuntu-24_04-lts'
        sku: 'server'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: 'StandardSSD_LRS'
        }
        deleteOption: 'Delete'
      }
      dataDisks: [
        {
          lun: 0
          name: '${clickHouseVmName}-data'
          createOption: 'Empty'
          diskSizeGB: clickHouseDataDiskSizeGB
          managedDisk: {
            storageAccountType: 'StandardSSD_LRS'
          }
          deleteOption: 'Delete'
        }
      ]
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: clickHouseNic.id
        }
      ]
    }
  }
  dependsOn: [
    clickHouseNic
  ]
}

resource eventGridTopic 'Microsoft.EventGrid/topics@2022-06-15' = {
  name: eventGridTopicName
  location: location
  properties: {
    inputSchema: 'CloudEventSchemaV1_0'
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    accessTier: 'Hot'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource backupContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: backupContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource unblockQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = {
  parent: queueService
  name: unblockQueueName
}

var storageConnection = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${listKeys(storage.id, '2023-05-01').keys[0].value};EndpointSuffix=${environment().suffixes.storage}'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource functionPlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: functionPlanName
  location: location
  kind: 'functionapp'
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: functionPlan.id
    httpsOnly: true
    clientAffinityEnabled: false
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: storageConnection
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'ENABLE_ORYX_BUILD'
          value: 'true'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'AZURE_SUBSCRIPTION_ID'
          value: subscription().subscriptionId
        }
        {
          name: 'NSG_RESOURCE_GROUP'
          value: resourceGroup().name
        }
        {
          name: 'NSG_NAME'
          value: sensorNsgName
        }
        {
          name: 'UNBLOCK_QUEUE'
          value: unblockQueueName
        }
        {
          name: 'CLOUDSENTINEL_ALLOWLIST'
          value: '${adminIpCidr},10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8,169.254.0.0/16'
        }
      ]
    }
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enableSoftDelete: true
    enablePurgeProtection: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

resource eventGridEndpointSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'eventgrid-topic-endpoint'
  properties: {
    value: eventGridTopic.properties.endpoint
  }
}

resource eventGridKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'eventgrid-topic-key'
  properties: {
    value: listKeys(eventGridTopic.id, '2022-06-15').key1
  }
}

resource llmKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (llmApiKey != '') {
  parent: keyVault
  name: 'llm-api-key'
  properties: {
    value: llmApiKey
  }
}

resource clickHousePasswordSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'clickhouse-password'
  properties: {
    value: clickHousePassword
  }
}

resource vaultPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.vaultcore.azure.net'
  location: 'global'
}

resource vaultPrivateDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: vaultPrivateDnsZone
  name: '${vnetName}-link'
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnet.id
    }
    registrationEnabled: false
  }
}

resource vaultPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: '${keyVaultName}-pe'
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'vault'
        properties: {
          privateLinkServiceId: keyVault.id
          groupIds: [
            'vault'
          ]
        }
      }
    ]
  }
}

resource vaultPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: vaultPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'vault'
        properties: {
          privateDnsZoneId: vaultPrivateDnsZone.id
        }
      }
    ]
  }
}

resource sensorKeyVaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, sensorVm.id, 'kv-secrets-user')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '4633458b-17de-408a-b874-0445c86b69e6'
    )
    principalId: sensorVm.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource sensorBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, sensorVm.id, 'blob-contributor')
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    )
    principalId: sensorVm.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

module nsgRole 'nsg-role.bicep' = {
  name: 'cloudsentinel-nsg-role'
  scope: subscription()
  params: {
    resourceGroupName: resourceGroup().name
    nsgName: sensorNsgName
    roleName: 'CloudSentinel NSG Rule Operator'
    assignableScope: resourceGroup().id
    principalId: functionApp.identity.principalId
  }
}

output sensorPublicIpAddress string = sensorPublicIp.properties.ipAddress
output sensorFqdn string = sensorPublicIp.properties.dnsSettings.fqdn
output sensorSshCommand string = 'ssh ${adminUsername}@${sensorPublicIp.properties.ipAddress}'
output managementSshCommand string = 'ssh -p 22222 ${adminUsername}@${sensorPublicIp.properties.ipAddress}'
output clickHousePrivateIp string = clickHouseNic.properties.ipConfigurations[0].properties.privateIPAddress
output eventGridTopicName string = eventGridTopic.name
output eventGridTopicEndpoint string = eventGridTopic.properties.endpoint
output functionAppName string = functionApp.name
output logAnalyticsName string = logAnalytics.name
output appInsightsName string = appInsights.name
output sensorNsgName string = sensorNsg.name
output keyVaultName string = keyVault.name
output storageAccountName string = storage.name
output backupContainerName string = backupContainerName
output resourceGroupName string = resourceGroup().name

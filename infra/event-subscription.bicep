targetScope = 'resourceGroup'

@description('Event Grid custom topic created by main.bicep.')
param eventGridTopicName string

@description('Function App created by main.bicep.')
param functionAppName string

@description('Event Grid trigger function name.')
param functionName string = 'block_ip'

@description('Event Grid subscription name.')
param subscriptionName string = 'cloudsentinel-block'

resource topic 'Microsoft.EventGrid/topics@2022-06-15' existing = {
  name: eventGridTopicName
}

resource blockSubscription 'Microsoft.EventGrid/topics/eventSubscriptions@2022-06-15' = {
  parent: topic
  name: subscriptionName
  properties: {
    destination: {
      endpointType: 'AzureFunction'
      resourceId: resourceId('Microsoft.Web/sites/functions', functionAppName, functionName)
    }
    filter: {
      includedEventTypes: [
        'CloudSentinel.BlockRequested'
      ]
      isSubjectCaseSensitive: false
    }
    retryPolicy: {
      maxDeliveryAttempts: 30
      eventTimeToLiveInMinutes: 1440
    }
  }
}

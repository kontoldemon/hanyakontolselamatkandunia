targetScope = 'subscription'

@description('Resource group that contains the sensor NSG.')
param resourceGroupName string

@description('Sensor NSG resource name.')
param nsgName string

@description('Custom role name.')
param roleName string

@description('Scope where the custom role may be assigned.')
param assignableScope string

@description('Function App managed identity principal ID.')
param principalId string

var roleDefinitionName = guid(subscription().id, roleName)

resource roleDefinition 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: roleDefinitionName
  properties: {
    roleName: roleName
    description: 'Create, read, and delete CloudSentinel block rules on one NSG.'
    type: 'CustomRole'
    permissions: [
      {
        actions: [
          'Microsoft.Network/networkSecurityGroups/read'
          'Microsoft.Network/networkSecurityGroups/securityRules/read'
          'Microsoft.Network/networkSecurityGroups/securityRules/write'
          'Microsoft.Network/networkSecurityGroups/securityRules/delete'
        ]
        notActions: []
        dataActions: []
        notDataActions: []
      }
    ]
    assignableScopes: [
      assignableScope
    ]
  }
}

resource sensorNsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' existing = {
  name: nsgName
  scope: resourceGroup(resourceGroupName)
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sensorNsg.id, principalId, roleName)
  scope: sensorNsg
  properties: {
    roleDefinitionId: roleDefinition.id
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

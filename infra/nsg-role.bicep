targetScope = 'subscription'

@description('Custom role name.')
param roleName string

@description('Scope where the custom role may be assigned.')
param assignableScope string

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

output roleDefinitionId string = roleDefinition.id

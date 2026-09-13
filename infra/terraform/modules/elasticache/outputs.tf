output "primary_endpoint" {
  value = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "port" {
  value = 6379
}

output "security_group_id" {
  value = aws_security_group.redis.id
}

output "primary_cache_cluster_id" {
  description = "The member cache cluster id (e.g. for CloudWatch `CacheClusterId` dimensions) of the primary node."
  value       = aws_elasticache_replication_group.this.member_clusters[0]
}

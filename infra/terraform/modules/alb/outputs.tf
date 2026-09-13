output "alb_dns_name" {
  value = aws_lb.this.dns_name
}

output "alb_arn_suffix" {
  description = "e.g. app/my-alb/50dc6c495c0c9188 — the format CloudWatch's ApplicationELB `LoadBalancer` dimension expects."
  value       = aws_lb.this.arn_suffix
}

output "alb_zone_id" {
  value = aws_lb.this.zone_id
}

output "alb_security_group_id" {
  value = aws_security_group.alb.id
}

output "api_target_group_arn" {
  value = aws_lb_target_group.api.arn
}

output "web_target_group_arn" {
  value = aws_lb_target_group.web.arn
}

output "https_listener_arn" {
  value = aws_lb_listener.https.arn
}

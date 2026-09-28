output "public_ip" {
  description = "Public IP of the server"
  value       = aws_instance.this.public_ip
}

output "ssh_command" {
  description = "Command to connect to the server"
  value       = "ssh -i ~/.ssh/env-builder ubuntu@${aws_instance.this.public_ip}"
}

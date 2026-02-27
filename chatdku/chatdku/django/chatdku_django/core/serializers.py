from rest_framework import serializers


class UploadFileSerializer(serializers.Serializer):
    file_=serializers.FileField()

    def validate_file_(self,value):
        max_size=1024*1024*10 # 10mb
        if not value.name.strip().endswith("pdf"):
            raise serializers.ValidationError("File should end with PDF")
        
        if value.size > max_size:
            raise serializers.ValidationError("File must be less than 10 mb")
        
        return value



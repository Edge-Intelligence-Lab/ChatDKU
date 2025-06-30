from rest_framework import serializers


class UploadFileSerializer(serializers.Serializer):
    file_=serializers.FileField()

    def validate_file_(self,value):
        if not value.name.strip().endswith("pdf"):
            raise serializers.ValidationError("File should end with PDF")
        
        return value

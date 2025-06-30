from rest_framework import serializers


class UploadFileSerializer(serializers.Serializer):
    file_=serializers.FileField()

    def folder_validation(self,value):
        if not value.name.endswith("pdf"):
            return serializers.ValidationError("File should end with PDF")
        
        return value

from rest_framework import serializers


from rest_framework import serializers

class SourceSerializer(serializers.Serializer):

    sources = serializers.ListField(
        child=serializers.CharField(), required=False, default=['ChatDKU']
    )

    def validate(self, data):
        docs = data.get('sources') or ['ChatDKU']
        try:

            if len(docs) == 1:
                search_mode = 1 if docs[0] != 'ChatDKU' else 0
            elif len(docs) > 1 and docs[0] == 'ChatDKU':
                search_mode = 2
            else:
                search_mode = 1

        except Exception as e:
            search_mode=0
        
        data['search_mode'] = search_mode
        data['docs']=docs
        return data

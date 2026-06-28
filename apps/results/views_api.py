from rest_framework.views import APIView; from rest_framework.permissions import IsAuthenticated; from rest_framework.response import Response
class ResultAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, exam_id, class_id):
        return Response({'status': 'ok'})

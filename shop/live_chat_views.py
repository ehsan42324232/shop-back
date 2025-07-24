                }, status=status.HTTP_400_BAD_REQUEST)

            # Get chat room
            try:
                chat_room = ChatRoom.objects.get(id=room_id)
            except ChatRoom.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'اتاق چت یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)

            # Update status
            old_status = chat_room.status
            chat_room.status = new_status
            chat_room.notes = notes
            
            if new_status == 'closed':
                chat_room.closed_at = timezone.now()
                chat_room.closed_by = request.user
            
            chat_room.save()

            # Notify participants about status change
            self._notify_status_change(chat_room, old_status, new_status)

            return Response({
                'success': True,
                'message': f'وضعیت چت به {self._get_status_text(new_status)} تغییر کرد',
                'data': {
                    'room_id': chat_room.id,
                    'old_status': old_status,
                    'new_status': new_status
                }
            })

        except Exception as e:
            logger.error(f"Error updating chat room status: {e}")
            return Response({
                'success': False,
                'message': 'خطا در بروزرسانی وضعیت چت'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _notify_status_change(self, chat_room, old_status, new_status):
        """
        Notify participants about status change
        """
        try:
            status_data = {
                'type': 'status_change',
                'room_id': chat_room.id,
                'old_status': old_status,
                'new_status': new_status,
                'status_text': self._get_status_text(new_status),
                'timestamp': timezone.now().isoformat()
            }

            async_to_sync(channel_layer.group_send)(
                f"chat_room_{chat_room.id}",
                {
                    'type': 'status_update',
                    'message': status_data
                }
            )
        except Exception as e:
            logger.error(f"Error notifying status change: {e}")

    def _get_status_text(self, status):
        """
        Get Persian text for status
        """
        status_map = {
            'active': 'فعال',
            'closed': 'بسته شده',
            'transferred': 'منتقل شده'
        }
        return status_map.get(status, 'نامشخص')

class ChatAnalyticsView(APIView):
    """
    Chat analytics for store owners
    """
    authentication_classes = [MallTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get chat analytics
        """
        try:
            # Get user's stores
            stores = Store.objects.filter(owner=request.user)
            
            analytics_data = {
                'total_chats': 0,
                'active_chats': 0,
                'closed_chats': 0,
                'average_response_time': 0,
                'customer_satisfaction': 0,
                'daily_chats': [],
                'popular_questions': []
            }

            for store in stores:
                store_chats = ChatRoom.objects.filter(store=store)
                
                analytics_data['total_chats'] += store_chats.count()
                analytics_data['active_chats'] += store_chats.filter(status='active').count()
                analytics_data['closed_chats'] += store_chats.filter(status='closed').count()

            return Response({
                'success': True,
                'data': analytics_data
            })

        except Exception as e:
            logger.error(f"Error retrieving chat analytics: {e}")
            return Response({
                'success': False,
                'message': 'خطا در دریافت آمار چت'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
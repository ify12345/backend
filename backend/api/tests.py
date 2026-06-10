from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Note


class AuthTests(APITestCase):
    def test_register_creates_user(self):
        url = reverse("register")
        response = self.client.post(
            url, {"username": "alice", "password": "s3cret-pass"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="alice").exists())
        # password must never be returned
        self.assertNotIn("password", response.data)

    def test_token_obtain_returns_access_and_refresh(self):
        User.objects.create_user(username="bob", password="s3cret-pass")
        url = reverse("get_token")
        response = self.client.post(
            url, {"username": "bob", "password": "s3cret-pass"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_token_obtain_rejects_bad_password(self):
        User.objects.create_user(username="carol", password="s3cret-pass")
        url = reverse("get_token")
        response = self.client.post(
            url, {"username": "carol", "password": "wrong"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NoteTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dave", password="s3cret-pass")
        self.other = User.objects.create_user(username="erin", password="s3cret-pass")

    def authenticate(self, user):
        # force_authenticate bypasses JWT for the test; we test auth separately above
        self.client.force_authenticate(user=user)

    def test_notes_require_authentication(self):
        response = self.client.get(reverse("note-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_note_sets_author_to_current_user(self):
        self.authenticate(self.user)
        response = self.client.post(
            reverse("note-list"),
            {"title": "My note", "content": "hello"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        note = Note.objects.get()
        self.assertEqual(note.author, self.user)
        self.assertEqual(note.title, "My note")

    def test_list_returns_only_own_notes(self):
        Note.objects.create(author=self.user, title="mine", content="x")
        Note.objects.create(author=self.other, title="theirs", content="y")
        self.authenticate(self.user)
        response = self.client.get(reverse("note-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [n["title"] for n in response.data]
        self.assertEqual(titles, ["mine"])

    def test_cannot_delete_another_users_note(self):
        note = Note.objects.create(author=self.other, title="theirs", content="y")
        self.authenticate(self.user)
        response = self.client.delete(reverse("note-delete", args=[note.pk]))
        # not in dave's queryset -> 404, and the note still exists
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Note.objects.filter(pk=note.pk).exists())

    def test_can_delete_own_note(self):
        note = Note.objects.create(author=self.user, title="mine", content="x")
        self.authenticate(self.user)
        response = self.client.delete(reverse("note-delete", args=[note.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Note.objects.filter(pk=note.pk).exists())

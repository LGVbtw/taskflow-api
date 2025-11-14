from django.db import migrations, models
import django.db.models.deletion


TASK_TYPES = [
    ("epic", "Epic"),
    ("story", "User Story"),
    ("feature", "Feature"),
    ("task", "Tâche"),
    ("subtask", "Sous-tâche"),
]


def seed_task_types(apps, schema_editor):
    TaskType = apps.get_model('tasks', 'TaskType')
    Task = apps.get_model('tasks', 'Task')

    for order, (code, label) in enumerate(TASK_TYPES):
        TaskType.objects.update_or_create(
            code=code,
            defaults={
                'label': label,
                'order': order * 10,
            },
        )

    default_type = TaskType.objects.get(code='task')
    Task.objects.filter(task_type__isnull=True).update(task_type=default_type)


def unseed_task_types(apps, schema_editor):
    TaskType = apps.get_model('tasks', 'TaskType')
    TaskType.objects.filter(code__in=[code for code, _ in TASK_TYPES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0010_message'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=32, unique=True)),
                ('label', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('order', models.PositiveIntegerField(default=0)),
            ],
            options={
                'ordering': ['order', 'id'],
            },
        ),
        migrations.AddField(
            model_name='task',
            name='parent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='tasks.task'),
        ),
        migrations.AddField(
            model_name='task',
            name='task_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='tasks', to='tasks.tasktype'),
        ),
        migrations.RunPython(seed_task_types, unseed_task_types),
    ]

from django.core.management.base import BaseCommand
from warehouse.models import Warehouse, ConstructionStage, Material, StageLimit

class Command(BaseCommand):
    help = 'Додає етапи будівництва до ВСІХ складів'

    def handle(self, *args, **options):
        self.stdout.write("🔧 Виправлення етапів...")

        warehouses = Warehouse.objects.all()
        
        # Шукаємо бетон (або перший ліпший матеріал)
        concrete = Material.objects.filter(name__icontains="Бетон").first()
        if not concrete:
            self.stdout.write(self.style.ERROR("❌ Не знайдено матеріалу 'Бетон'. Спочатку запустіть seed_data!"))
            return

        for wh in warehouses:
            self.stdout.write(f"👉 Обробка складу: {wh.name}")
            
            # 1. Створюємо етапи
            stage_1, _ = ConstructionStage.objects.get_or_create(name="1. Фундамент", warehouse=wh)
            stage_2, _ = ConstructionStage.objects.get_or_create(name="2. Стіни та Колони", warehouse=wh)
            
            # 2. Додаємо ліміти (щоб система знала, що тут потрібен бетон)
            StageLimit.objects.get_or_create(
                stage=stage_1, 
                material=concrete, 
                defaults={'construct_type': 'horizontal', 'planned_quantity': 100}
            )
            
            StageLimit.objects.get_or_create(
                stage=stage_2, 
                material=concrete, 
                defaults={'construct_type': 'vertical', 'planned_quantity': 50}
            )

        self.stdout.write(self.style.SUCCESS(f"✅ Готово! Етапи додано до {warehouses.count()} складів."))